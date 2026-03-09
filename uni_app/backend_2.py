from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

app = FastAPI()

# 允许所有跨域请求（仅开发环境）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 返回格式 ====================

class DetectionItem(BaseModel):
    """单个检测项 - 对应PPT中的简化版类别"""
    class_id: int           # 0-9，对应PPT中的10个类别
    class_name: str         # "oc"/"1st"/"2nd"/"3rd"/"4th"/"5th"/"6th"/"7th"/"space"/"caries"
    confidence: float       # 置信度 0-1
    bbox: List[float]       # 边界框 [x1, y1, x2, y2]
    # 可选：如果是牙齿(1-7)，可以返回具体FDI编号和恒乳牙类型
    fdi_number: Optional[str] = None    # 如"16"(恒牙)或"51"(乳牙)
    tooth_type: Optional[str] = None    # "permanent"(恒牙)或"primary"(乳牙)

class DetectionResult(BaseModel):
    """完整检测结果"""
    success: bool           # 是否成功
    message: str            # 提示信息
    image_name: str         # 图片文件名
    total_detections: int   # 检测到的目标总数
    teeth_count: int        # 牙齿数量（不含space和caries）
    caries_count: int       # 龋齿数量
    detections: List[DetectionItem]  # 所有检测项列表

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

@app.post("/upload", response_model=DetectionResult)
async def upload_image(file: UploadFile = File(...)):
    """
    上传口腔图片，返回牙齿检测和龋齿识别结果
    返回格式严格按PPT约定：class_id 0-9，对应10个类别
    """
    contents = await file.read()
    image_name = file.filename
    
    # TODO: 这里接入模型推理
    # 现在用mock数据演示返回格式
    
    mock_detections = [
        DetectionItem(
            class_id=6,
            class_name="6th",
            confidence=0.95,
            bbox=[100.5, 200.3, 150.8, 280.7],
            fdi_number="16",
            tooth_type="permanent"
        ),
        DetectionItem(
            class_id=1,
            class_name="1st",
            confidence=0.92,
            bbox=[200.0, 180.0, 240.0, 260.0],
            fdi_number="11",
            tooth_type="permanent"
        ),
        DetectionItem(
            class_id=9,  # 龋齿
            class_name="caries",
            confidence=0.88,
            bbox=[110.0, 210.0, 140.0, 250.0],
            fdi_number=None,  # caries没有FDI编号，它属于某颗牙齿
            tooth_type=None
        ),
        DetectionItem(
            class_id=8,  # 空位
            class_name="space",
            confidence=0.78,
            bbox=[300.0, 190.0, 340.0, 250.0],
            fdi_number=None,
            tooth_type=None
        )
    ]
    
    # 统计数量
    teeth_count = len([d for d in mock_detections if d.class_id in range(1, 8)])
    caries_count = len([d for d in mock_detections if d.class_id == 9])
    
    return DetectionResult(
        success=True,
        message="检测成功",
        image_name=image_name,
        total_detections=len(mock_detections),
        teeth_count=teeth_count,
        caries_count=caries_count,
        detections=mock_detections
    )

@app.get("/")
async def root():
    return {
        "message": "Dental Detection API", 
        "version": "1.0",
        "classes": CLASS_NAMES  # 返回类别定义供前端参考
    }

if __name__ == "__main__":
    uvicorn.run("backend_2:app", host="0.0.0.0", port=8080, reload=True)