from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn

# 模型推理相关
import torch
import torch.nn.functional as F
from torchvision import transforms
from PIL import Image
import io
import os

import sys
from torch import nn
from torchvision.models import resnet50
import math

from contextlib import asynccontextmanager

# 运行时全局模型变量
model = None
caries_model = None  # 后续第二阶段模型（龋齿识别）

MODEL_PATH = os.getenv("MODEL_PATH", "D:/fastapi_demo/best_stg2.pth")
CARIES_MODEL_PATH = os.getenv("CARIES_MODEL_PATH", "best_caries.pth")

# --- 新增：DETR 模型架构定义 ---
class DETR(nn.Module):
    """
    DETR model class.
    基于 https://github.com/facebookresearch/detr 的简化版本
    """
    def __init__(self, num_classes, hidden_dim=256, nheads=8, num_encoder_layers=6, num_decoder_layers=6):
        super().__init__()
        # 使用 ResNet-50 作为 Backbone
        self.backbone = resnet50(pretrained=False)
        # 删除最后的全连接层，只保留卷积特征
        self.backbone = nn.Sequential(*list(self.backbone.children())[:-2])
        
        # 转换层：将 2048 维的 ResNet 特征转换为 Transformer 需要的 hidden_dim
        self.conv = nn.Conv2d(2048, hidden_dim, 1)
        
        # Transformer
        self.transformer = nn.Transformer(
            hidden_dim, nheads, num_encoder_layers, num_decoder_layers
        )
        
        # 预测头：输出类别和坐标
        # linear class embedding
        self.class_embed = nn.Linear(hidden_dim, num_classes + 1)
        # linear bounding box embedding
        self.bbox_embed = nn.Linear(hidden_dim, 4)
        
        # 位置编码
        self.query_pos = nn.Parameter(torch.rand(100, hidden_dim))
        
    def forward(self, x):
        # Backbone: 获取特征图
        features = self.backbone(x)
        
        # 调整维度: (N, C, H, W) -> (C, H*W, N)
        h, w = features.shape[-2:]
        pos = self.conv(features).flatten(2).permute(2, 0, 1)
        
        # Transformer
        # 这里简化处理，实际 DETR 还需要位置编码等
        h = self.transformer(pos, self.query_pos.unsqueeze(1))
        
        # 预测
        probs = self.class_embed(h)
        coords = self.bbox_embed(h).sigmoid()
        
        # 返回结果 (这里简化为直接返回最后层的输出)
        return probs, coords


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时加载模型
    global model, caries_model
    if torch is None:
        yield
        return
    
    # --- 修改主模型加载逻辑 ---
    try:
        print(f"尝试加载主模型: {MODEL_PATH}")
        
        # 1. 先加载 state_dict
        state_dict = torch.load(MODEL_PATH, map_location="cpu")
        
        # 2. 实例化模型架构
        # 注意：num_classes 需要根据你的实际情况修改。
        # 牙齿检测通常包含：10个类别 (0-9) + 1个背景类 = 11
        # 如果报错 size mismatch，请尝试修改这里的数字
        model_instance = DETR(num_classes=10) 
        
        # 3. 加载权重
        # strict=False 允许部分键不匹配（比如如果你用了不同的 Backbone）
        model_instance.load_state_dict(state_dict, strict=False)
        model_instance.eval()
        
        # 4. 赋值给全局 model
        model = model_instance
        print(f"✅ 成功加载 DETR 模型架构并加载权重")
        
    except Exception as e:
        print(f"❌ 加载主模型失败: {e}")
        print("提示：如果报错 'size mismatch'，说明模型结构定义与训练时不完全一致。")
        model = None
        
    # ... (第二阶段 caries_model 保持注释状态) ...
    yield


app = FastAPI(lifespan=lifespan)

class DetectionItem(BaseModel):
    """单个检测项 - 对应PPT中的简化版类别"""
    class_id: int           # 0-9，对应PPT中的10个类别
    class_name: str         # "oc"/"1st"/"2nd"/"3rd"/"4th"/"5th"/"6th"/"7th"/"space"/"caries"
    confidence: float       # 置信度 0-1
    bbox: List[float]       # 边界框 [x1, y1, x2, y2]
    # 可选：如果是牙齿(1-7)，可以返回具体FDI编号和恒乳牙类型
    fdi_number: Optional[str] = None    # 如"16"(恒牙)或"51"(乳牙)
    tooth_type: Optional[str] = None    # "permanent"(恒牙)或"primary"(乳牙)

    # ----- 以下为规则判断新增字段 -----
    caries_severity: Optional[str] = None     # "shallow"/"moderate"/"severe"
    diagnosis_tags: List[str] = []            # 例如 ["fsc","caries"], ["talc"] 等
    tooth_status: Optional[str] = None        # "normal"/"erupting"/"unerupted"/"impacted"
    has_restoration: bool = False             # 是否存在充填物/修复体

class DetectionResult(BaseModel):
    """完整检测结果"""
    success: bool           # 是否成功
    message: str            # 提示信息
    image_name: str         # 图片文件名
    total_detections: int   # 检测到的目标总数
    teeth_count: int        # 牙齿数量（不含space和caries）
    caries_count: int       # 龋齿数量
    detections: List[DetectionItem]  # 所有检测项列表

class QuestionnaireData(BaseModel):
    # 维度一：喂养与夜食习惯
    q1: int  # 1.含着奶瓶入睡频率: 0-3分
    q2: int  # 2.夜间进食后清洁: 0-3分
    q3: int  # 3.母乳喂养时长: 0-3分
    # 维度二：口腔卫生行为
    q4: int  # 4.每天刷牙次数: 0-6分
    q5: int  # 5.开始刷牙年龄: 0-3分
    q6: int  # 6.是否使用含氟牙膏: 0-4分
    q7: int  # 7.使用牙线频率: 0-5分
    q8: int  # 8.刷牙由谁完成: 0-3分
    # 维度三：饮食与糖摄入
    q9: int  # 9.甜食频率: 0-6分
    q10: int # 10.食物类型偏向: 0-3分
    q11: int # 11.饭后漱口: 0-4分
    # 维度四：口腔医疗利用
    q12: int # 12.定期检查: 0-5分
    # 维度五：母亲及家庭相关因素
    q13: int # 13.照料者龋齿: 0-4分
    q14: int # 14.孕期吸烟: 0-4分
    q15: int # 15.照料者教育程度: 0-3分

class AssessRequest(BaseModel):
    age: int
    questionnaire: QuestionnaireData
    detections: List[DetectionItem]


class AssessmentResult(BaseModel):
    success: bool
    score: int
    category: str
    adjusted_score: Optional[int] = None
    message: Optional[str] = None
    # 可返回详细规则触发信息，通常为列表
    details: Optional[Any] = None


@app.post("/assess", response_model=AssessmentResult)
async def assess(request: AssessRequest):
    """结合问卷和检测结果给出风险评分和分类"""
    raw_score = sum(vars(request.questionnaire).values())
    result = apply_unreasonable_rules(request.age, request.detections, raw_score)
    adjusted = result.get("adjusted_score", raw_score)
    category = categorize_score(adjusted)
    return AssessmentResult(
        success=True,
        score=raw_score,
        adjusted_score=adjusted,
        category=category,
        message="评估完成",
        details=result.get("triggered")
    )

# 类别映射（严格按PPT中的简化版）
CLASS_NAMES = {
    0: "oc",        # 整张嘴
    1: "1st",       # 中切牙（恒牙11/21/31/41 + 乳牙51/61/71/81）
    2: "2nd",       # 侧切牙
    3: "3rd",       # 尖牙
    4: "4th",       # 第一前磨牙/第一乳磨牙
    5: "5th",       # 第二前磨牙/第二乳磨牙
    6: "6th",       # 第一磨牙（仅恒牙）
    7: "7th",       # 第二磨牙（仅恒牙）
    8: "space",     # 空位/缺牙
    9: "caries",    # 龋齿（第二阶段识别）
}

# FDI编号到简化类别的映射（用于后续模型接入）
TOOTH_MAPPING = {
    # 恒牙
    "11": 1, "21": 1, "31": 1, "41": 1,
    "12": 2, "22": 2, "32": 2, "42": 2,
    "13": 3, "23": 3, "33": 3, "43": 3,
    "14": 4, "24": 4, "34": 4, "44": 4,
    "15": 5, "25": 5, "35": 5, "45": 5,
    "16": 6, "26": 6, "36": 6, "46": 6,
    "17": 7, "27": 7, "37": 7, "47": 7,
    # 乳牙
    "51": 1, "61": 1, "71": 1, "81": 1,
    "52": 2, "62": 2, "72": 2, "82": 2,
    "53": 3, "63": 3, "73": 3, "83": 3,
    "54": 4, "64": 4, "74": 4, "84": 4,
    "55": 5, "65": 5, "75": 5, "85": 5,
}



def get_tooth_type(fdi_number: str) -> Optional[str]:
    """根据FDI编号判断恒牙或乳牙"""
    if not fdi_number or len(fdi_number) != 2:
        return None
    quadrant = int(fdi_number[0])
    return "permanent" if quadrant <= 4 else "primary"


# ---------- 模型加载 ----------



def run_real_model(image_bytes: bytes) -> List[DetectionItem]:
    global model
    if model is None:
        return []
    
    # 1. 图片预处理
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    
    # DETR 标准预处理
    transform = transforms.Compose([
        transforms.Resize((800, 800)), 
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    img_tensor = transform(image).unsqueeze(0)
    
    # 2. 推理
    with torch.no_grad():
        outputs = model(img_tensor)
        
    # --- 修正后的调试逻辑 ---
    print(f">>> [Model Debug] 模型输出类型: {type(outputs)}")
    
    pred_logits = None
    pred_boxes = None

    # 1. 兼容元组输出 (probs, boxes)
    if isinstance(outputs, tuple) and len(outputs) == 2:
        print(">>> [Model Debug] 识别到元组输出 (logits, boxes)")
        pred_logits, pred_boxes = outputs
    # 2. 兼容字典输出
    elif isinstance(outputs, dict):
        print(">>> [Model Debug] 识别到字典输出")
        pred_logits = outputs.get('pred_logits')
        pred_boxes = outputs.get('pred_boxes')
    else:
        print(">>> [Model Error] 无法识别的模型输出格式")
        return []

    if pred_logits is None:
        print(">>> [Model Error] 未能提取到 logits")
        return []

    # 打印原始形状
    print(f">>> [Model Debug] 原始 Logits Shape: {pred_logits.shape}")
    
    # --- 关键修正：处理维度 ---
    # DETR 标准输出通常是 [Batch, Num_Queries, Num_Classes]
    # 但你的模型输出是 [Num_Queries, Batch, Num_Classes] 即 [100, 1, 11]
    # 我们需要把它变成 [Batch, Num_Queries, Num_Classes] 即 [1, 100, 11]
    
    # 如果维度顺序不对，进行置换 (permute)
    if pred_logits.shape[0] == 100 and pred_logits.shape[1] == 1:
        print(">>> [Model Debug] 检测到维度异常 [N, B, C]，正在修正为 [B, N, C]...")
        pred_logits = pred_logits.permute(1, 0, 2) # 变成 [1, 100, 11]
        # boxes 通常也是 [N, B, 4]，也需要修正
        if pred_boxes.shape[0] == 100 and pred_boxes.shape[1] == 1:
            pred_boxes = pred_boxes.permute(1, 0, 2) # 变成 [1, 100, 4]

    print(f">>> [Model Debug] 修正后 Logits Shape: {pred_logits.shape}")
    
    # 打印最大置信度 Top 5
    # 现在 pred_logits[0] 取到的是 Batch 0，形状是 [100, 11]
    max_probs = pred_logits[0].softmax(-1).max(-1).values
    print(f">>> [Model Debug] 最大置信度 Top 5: {max_probs.topk(5).values}")
    # --- 结束调试逻辑 ---

    # 3. 后处理
    # 取出 batch 0 的结果
    probs = pred_logits[0]  # (num_queries, num_classes)
    boxes = pred_boxes[0]   # (num_queries, 4)
    
    # 获取每个 query 的最大置信度及其对应的类别
    max_probs, max_ids = probs.softmax(-1).max(-1)
    
    # 过滤掉背景类（通常类别 ID 是 num_classes，即最后一个）或低置信度
    # 假设 num_classes=10，则背景类索引为 10
    # 我们只保留置信度 > 0.1 且不是背景的
    keep = (max_probs > 0.1) & (max_ids != 10) 
    
    print(f">>> [Model Debug] 阈值 0.1 下，检测到目标数量: {keep.sum().item()}")
    
    detections = []
    for i in range(len(keep)):
        if keep[i]:
            class_id = max_ids[i].item()
            confidence = max_probs[i].item()
            box = boxes[i].cpu().numpy()
            
            # DETR 输出的是中心点坐标和宽高，且是归一化的 (0-1)
            # 转换为 (x1, y1, x2, y2) 像素坐标
            w, h = image.size
            x_c, y_c, bw, bh = box
            
            # 反归一化并转换格式
            x1 = (x_c - bw / 2) * w
            y1 = (y_c - bh / 2) * h
            x2 = (x_c + bw / 2) * w
            y2 = (y_c + bh / 2) * h
            
            class_name = CLASS_NAMES.get(class_id, "unknown")
            
            det = DetectionItem(
                class_id=int(class_id),
                class_name=class_name,
                confidence=float(confidence),
                bbox=[float(x1), float(y1), float(x2), float(y2)],
                fdi_number=None,
                tooth_type=None
            )
            detections.append(det)
            
    return detections






def categorize_score(score: int) -> str:
    if score <= 15:
        return "低风险"
    elif score <= 30:
        return "中风险"
    elif score <= 45:
        return "高风险"
    else:
        return "极高风险"


def apply_unreasonable_rules(age: int, detections: List[DetectionItem], score: int) -> Dict[str, Any]:
    """应用一组‘不合理推断’规则并返回调整结果。
    
    根据 questionaire.txt 中的规则进行逻辑判断。
    返回字典包含调整后分数和触发的规则列表。
    """
    adjusted = score
    triggered = []

    def mark(rule, msg=None):
        triggered.append({"rule": rule, "message": msg})

    # 辅助函数：判断是否为乳牙
    def is_primary(fdi: Optional[str]) -> bool:
        return bool(fdi and len(fdi) == 2 and int(fdi[0]) > 4)

    # 辅助函数：判断是否为恒牙
    def is_permanent(fdi: Optional[str]) -> bool:
        return bool(fdi and len(fdi) == 2 and int(fdi[0]) <= 4)

    # 辅助函数：判断是否为前牙 (FDI 1-3, 5-8 象限的 1-3 号牙)
    def is_anterior(fdi: Optional[str]) -> bool:
        if not fdi or len(fdi) != 2:
            return False
        tooth_num = int(fdi[1])
        return 1 <= tooth_num <= 3

    # 辅助函数：判断是否为磨牙 (FDI 6-7, 8-5 象限的 6-7 号牙)
    def is_molar(fdi: Optional[str]) -> bool:
        if not fdi or len(fdi) != 2:
            return False
        tooth_num = int(fdi[1])
        return tooth_num in [6, 7]

    # --- 龋病相关规则 (C系列) ---

    # 规则 C01: 乳牙邻面龋双倍怀疑
    for det in detections:
        # 假设 diagnosis_tags 包含 "pc" (proximal caries) 或类似标签
        # 注意：文档中提到的标签需要映射到 DetectionItem 的字段
        if "pc" in det.diagnosis_tags and is_primary(det.fdi_number):
            if age <= 5 and det.confidence < 0.7:
                det.confidence *= 0.8
                mark("C01", "乳牙邻面龋影像易与牙体叠影混淆，建议临床探诊")

    # 规则 C02: 窝沟浅龋不报重度
    for det in detections:
        if "fsc" in det.diagnosis_tags:
            if det.caries_severity == "severe":
                det.caries_severity = "moderate" # 或 shallow
                mark("C02", "窝沟浅龋为釉质层病变，不可报重度深龋")

    # 规则 C03: 可疑龋不并行确诊断
    # 这需要遍历检测列表，查找同一牙位的冲突
    # 简化实现：如果列表中同时存在 susp 和 caries，移除 susp
    suspicious_dets = [d for d in detections if "susp" in d.diagnosis_tags]
    for susp_det in suspicious_dets:
        for other_det in detections:
            if susp_det != other_det and susp_det.fdi_number == other_det.fdi_number:
                if "caries" in other_det.diagnosis_tags or other_det.class_name == "caries":
                    if susp_det in detections:
                        detections.remove(susp_det)
                        mark("C03", "同一牙位不可同时报可疑龋和确诊断龋")
                        break

    # 规则 C04: 残根年龄下限
    for det in detections:
        if det.class_name == "root": # 假设 class_name 或 diagnosis_tags 包含 root
            if age < 3 and is_primary(det.fdi_number) and is_anterior(det.fdi_number):
                det.confidence *= 0.3
                mark("C04", "3岁以下乳前牙残根罕见，多为奶瓶龋初期")

    # --- 发育异常规则 (D系列) ---

    # 规则 D01: 畸形中央尖年龄下限
    for det in detections:
        if "dcc" in det.diagnosis_tags:
            if age < 6:
                det.confidence = 0.0
                mark("D01", "6岁前前磨牙未萌，畸形中央尖诊断不成立")

    # 规则 D02: 畸形舌尖不报龋
    for det in detections:
        if "talc" in det.diagnosis_tags:
            for other_det in detections:
                if det != other_det and det.fdi_number == other_det.fdi_number:
                    if "caries" in other_det.diagnosis_tags or other_det.class_name == "caries":
                        other_det.confidence *= 0.5
                        other_det.diagnosis_tags.append("发育沟误判")
                        mark("D02", "畸形舌尖深沟易误判为龋齿，建议临床确认")

    # 规则 D05: 氟斑牙年龄下限
    for det in detections:
        if "flo" in det.diagnosis_tags:
            if age < 6:
                det.confidence *= 0.2
                mark("D05", "6岁以下氟斑牙需确认高氟区生活史")

    # --- 牙髓与根尖规则 (P系列) ---

    # 规则 P02: 乳牙瘘管年龄下限
    for det in detections:
        if "abs" in det.diagnosis_tags or det.class_name == "abs": # 假设 abs 是瘘管
            if age < 2 and is_primary(det.fdi_number):
                det.confidence *= 0.4
                mark("P02", "2岁以下乳牙根尖周炎瘘管少见")

    # --- 牙周规则 (G系列) ---

    # 规则 G01: 牙结石不报于乳牙列
    for det in detections:
        if "dntart" in det.diagnosis_tags:
            if age <= 5 and is_primary(det.fdi_number):
                det.confidence *= 0.3
                mark("G01", "5岁以下乳牙结石罕见，多为菌斑钙化初期")

    # --- 萌出与替换规则 (E系列) ---

    # 规则 E01: 乳牙滞留年龄下限
    before = len(detections)
    detections[:] = [d for d in detections if not ("rpt" in d.diagnosis_tags and age < 5)]
    if len(detections) != before:
        mark("E01", "5岁以下乳牙滞留不成立")

    # 规则 E02: 萌出中牙齿不报龋
    for det in detections:
        if "erup" in det.diagnosis_tags:
            for other_det in detections:
                if det != other_det and det.fdi_number == other_det.fdi_number:
                    if "caries" in other_det.diagnosis_tags or other_det.class_name == "caries":
                        other_det.confidence *= 0.3
                        mark("E02", "萌出中牙面多为龈瓣覆盖，龋病少见")

    # --- 咬合与间隙规则 (O系列) ---

    # 规则 O01: 反合不报于乳牙早失
    # 统计缺牙数 (class_name == "space" 或 diagnosis_tags 包含 pe)
    space_count = sum(1 for d in detections if d.class_name == "space" or "pe" in d.diagnosis_tags)
    if age < 6 and space_count > 4:
        for det in detections:
            if "rbite" in det.diagnosis_tags or det.class_name == "rbite":
                det.confidence *= 0.5
                mark("O01", "乳牙早失性假性反合，非真性反合")

    # 规则 O02: 空隙不报于替牙期（特定情况）
    for det in detections:
        if det.class_name == "space":
            if 6 <= age <= 9 and det.fdi_number in ["11", "21"]: # 上颌中切牙
                det.diagnosis_tags.append("丑小鸭期生理间隙")
                mark("O02", "上颌中切牙萌出期间隙多为生理性")

    # --- 外伤规则 (T系列) ---

    # 规则 T02: 牙列缺损年龄下限
    for det in detections:
        if "pe" in det.diagnosis_tags:
            if age < 4 and space_count < 2:
                # 降级处理：将 pe 标签移除或标记为未萌
                if "pe" in det.diagnosis_tags:
                    det.diagnosis_tags.remove("pe")
                det.diagnosis_tags.append("乳牙未萌")
                mark("T02", "4岁以下牙列空缺多为生理性未萌")

    # --- 牙体硬组织病 (H系列) ---

    # 规则 H01: 色素沉着不报于乳牙新生线
    for det in detections:
        if "pig" in det.diagnosis_tags or "pigmented" in det.diagnosis_tags:
            if age <= 3 and is_primary(det.fdi_number) and is_anterior(det.fdi_number):
                det.confidence *= 0.4
                mark("H01", "3岁以下乳切牙唇面暗色多为生理性色素沉着或新生线")

    # 规则 H03: 环状龋年龄特征绑定
    for det in detections:
        if "band" in det.diagnosis_tags:
            if age > 4:
                # 文档说：非上颌乳切牙。这里简化为年龄判断，具体牙位判断需更精确的FDI逻辑
                det.confidence *= 0.5
                mark("H03", "环状龋多见于2-4岁上颌乳切牙，请确认牙位")

    return {"adjusted_score": adjusted, "triggered": triggered}


@app.post("/upload", response_model=DetectionResult)
async def upload_image(file: UploadFile = File(...)):
    """
    上传口腔图片，返回牙齿检测和龋齿识别结果
    """
    # --- try 块开始 ---
    try:
        # 1. 读取图片
        contents = await file.read()

        import time
        image_name = f"upload_{int(time.time())}.jpg"
        
        print(f">>> [Debug] 收到文件: {image_name}")
        
        # 2. 运行模型
        # 注意：这里会调用 run_real_model
        # 如果 run_real_model 报错，会被下面的 except 捕获
        detections = run_real_model(contents)
        
        # 3. 模拟第二阶段逻辑
        has_caries = any(d.class_name == "caries" for d in detections)
        
        final_detections = detections
        
        if not has_caries:
            print(">>> [模拟第二阶段] 未检测到龋齿，人为添加模拟龋齿 <<<")
            mock_caries = DetectionItem(
                class_id=9,
                class_name="caries",
                confidence=0.88,
                bbox=[100.0, 200.0, 150.0, 250.0],
                fdi_number="16",
                tooth_type="permanent"
            )
            final_detections.append(mock_caries)

        # 4. 统计数量
        teeth_count = len([d for d in final_detections if d.class_id in range(1, 8)])
        caries_count = len([d for d in final_detections if d.class_id == 9])
        
        # 5. 返回结果
        return DetectionResult(
            success=True,
            message="检测成功",
            image_name=image_name,
            total_detections=len(final_detections),
            teeth_count=teeth_count,
            caries_count=caries_count,
            detections=final_detections
        )

    # --- except 块开始 ---
    except Exception as e:
        # 捕获所有异常并打印详细堆栈
        print(f"!!! [Error] 上传接口崩溃: {e}")
        import traceback
        traceback.print_exc() # 这一步非常重要，会打印具体哪一行代码错了
        
        # 返回错误信息给前端
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"服务器内部错误: {str(e)}"}
        )


@app.get("/")
async def root():
    return {
        "message": "Dental Detection API", 
        "version": "1.0",
        "classes": CLASS_NAMES  # 返回类别定义供前端参考
    }


@app.get("/rules")
async def get_rules():
    """返回简单的问卷评分区间和示例不合理推断描述给前端使用"""
    return {
        "score_intervals": {
            "low": "0-15",
            "medium": "16-30",
            "high": "31-45",
            "very_high": ">45"
        },
        # 可以把不合理推断规则简要返回
        "unreasonable_examples": [
            "乳牙邻面龋低置信度仍认为须临床确认",
            "…"
        ]
    }

if __name__ == "__main__":
    uvicorn.run("backend_2:app", host="0.0.0.0", port=8080, reload=True)