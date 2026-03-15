<template>
  <view class="container">
    <text class="header">儿童龋病风险评估问卷</text>
    <scroll-view scroll-y style="height: 80vh">
      <!-- age input -->
      <view class="field section-title">
        <text class="label">基本信息</text>
      </view>
      <view class="field">
        <text class="question-text">孩子年龄（岁）</text>
        <input v-model.number="age" type="digit" class="input-box" placeholder="请输入年龄"/>
      </view>

      <!-- 维度一 -->
      <view class="field section-title">
        <text class="label">维度一：喂养与夜食习惯</text>
      </view>
      <view v-for="n in 3" :key="n" class="field question-item">
        <text class="question-text">{{ questions[n] }}</text>
        <picker mode="selector" :range="answerOptions[n]" range-key="text" @change="onAnswerChange(n, $event)">
          <view class="picker">
            {{ getSelectedText(n) }}
          </view>
        </picker>
      </view>

      <!-- 维度二 -->
      <view class="field section-title">
        <text class="label">维度二：口腔卫生行为</text>
      </view>
      <view v-for="n in [4,5,6,7,8]" :key="n" class="field question-item">
        <text class="question-text">{{ questions[n] }}</text>
        <picker mode="selector" :range="answerOptions[n]" range-key="text" @change="onAnswerChange(n, $event)">
          <view class="picker">
            {{ getSelectedText(n) }}
          </view>
        </picker>
      </view>

      <!-- 维度三 -->
      <view class="field section-title">
        <text class="label">维度三：饮食与糖摄入</text>
      </view>
      <view v-for="n in [9,10,11]" :key="n" class="field question-item">
        <text class="question-text">{{ questions[n] }}</text>
        <picker mode="selector" :range="answerOptions[n]" range-key="text" @change="onAnswerChange(n, $event)">
          <view class="picker">
            {{ getSelectedText(n) }}
          </view>
        </picker>
      </view>

      <!-- 维度四 -->
      <view class="field section-title">
        <text class="label">维度四：口腔医疗利用</text>
      </view>
      <view class="field question-item" :key="12">
        <text class="question-text">{{ questions[12] }}</text>
        <picker mode="selector" :range="answerOptions[12]" range-key="text" @change="onAnswerChange(12, $event)">
          <view class="picker">
            {{ getSelectedText(12) }}
          </view>
        </picker>
      </view>

      <!-- 维度五 -->
      <view class="field section-title">
        <text class="label">维度五：母亲及家庭相关因素</text>
      </view>
      <view v-for="n in [13,14,15]" :key="n" class="field question-item">
        <text class="question-text">{{ questions[n] }}</text>
        <picker mode="selector" :range="answerOptions[n]" range-key="text" @change="onAnswerChange(n, $event)">
          <view class="picker">
            {{ getSelectedText(n) }}
          </view>
        </picker>
      </view>
      
      <view style="height: 100rpx;"></view> <!-- 底部占位 -->
    </scroll-view>
    
    <view class="footer-btn">
      <button type="primary" @click="submit" :loading="submitting" class="submit-btn">提交评估</button>
    </view>
  </view>
</template>

<script>
export default {
  data() {
    return {
      age: '',
      // 初始化问卷数据，避免undefined
      questionnaire: {
        q1: null, q2: null, q3: null, q4: null, q5: null,
        q6: null, q7: null, q8: null, q9: null, q10: null,
        q11: null, q12: null, q13: null, q14: null, q15: null
      },
      // 题目文本映射
      questions: {
        1: "1. 孩子是否经常含着奶瓶或乳头入睡？",
        2: "2. 孩子喝夜奶或夜间进食后，是否进行口腔清洁？",
        3: "3. 母乳喂养持续时间？",
        4: "4. 孩子目前每天刷牙几次？",
        5: "5. 孩子开始刷牙的年龄是？",
        6: "6. 孩子是否使用含氟牙膏？",
        7: "7. 孩子是否每天使用牙线清洁牙缝？",
        8: "8. 7岁前，孩子刷牙主要由谁完成？",
        9: "9. 孩子摄入甜点、含糖饮料或糖果的频率是？（正餐之外）",
        10: "10. 孩子日常摄入的食物类型偏向？",
        11: "11. 孩子饭后或进食后是否漱口？",
        12: "12. 孩子是否进行定期口腔检查？",
        13: "13. 孩子主要照料者目前是否有活动性龋齿？",
        14: "14. 母亲在怀孕期间是否吸烟？",
        15: "15. 母亲受教育程度？"
      },
      // 选项配置：text为显示文本，score为实际分值
      answerOptions: {
        1: [
          { text: "A. 从不或极少 (0分)", score: 0 },
          { text: "B. 有时 (1分)", score: 1 },
          { text: "C. 经常 (2分)", score: 2 },
          { text: "D. 几乎每天 (3分)", score: 3 }
        ],
        2: [
          { text: "A. 每次都清洁 (0分)", score: 0 },
          { text: "B. 经常清洁 (1分)", score: 1 },
          { text: "C. 偶尔清洁 (2分)", score: 2 },
          { text: "D. 从不清洁 (3分)", score: 3 }
        ],
        3: [
          { text: "A. 从未或<12个月 (0分)", score: 0 },
          { text: "B. 12-18个月 (1分)", score: 1 },
          { text: "C. 19-24个月 (2分)", score: 2 },
          { text: "D. >24个月 (3分)", score: 3 }
        ],
        4: [
          { text: "A. ≥2次/天 (0分)", score: 0 },
          { text: "B. 1次/天 (2分)", score: 2 },
          { text: "C. <1次/天 (4分)", score: 4 },
          { text: "D. 从不刷牙 (6分)", score: 6 }
        ],
        5: [
          { text: "A. ≤1岁 (0分)", score: 0 },
          { text: "B. 1-2岁 (1分)", score: 1 },
          { text: "C. 2-3岁 (2分)", score: 2 },
          { text: "D. 3岁以后 (3分)", score: 3 }
        ],
        6: [
          { text: "A. 每次都用 (0分)", score: 0 },
          { text: "B. 有时用 (2分)", score: 2 },
          { text: "C. 从不用 (4分)", score: 4 },
          { text: "D. 不清楚 (3分)", score: 3 }
        ],
        7: [
          { text: "A. 每天1次及以上 (0分)", score: 0 },
          { text: "B. 每周2-3次 (2分)", score: 2 },
          { text: "C. 偶尔使用 (4分)", score: 4 },
          { text: "D. 从未使用 (5分)", score: 5 }
        ],
        8: [
          { text: "A. 全程家长帮助 (0分)", score: 0 },
          { text: "B. 家长+孩子 (1分)", score: 1 },
          { text: "C. 完全自己刷 (3分)", score: 3 }
        ],
        9: [
          { text: "A. ≤2次/周 (0分)", score: 0 },
          { text: "B. 3-6次/周 (2分)", score: 2 },
          { text: "C. 1-2次/天 (4分)", score: 4 },
          { text: "D. ≥3次/天 (6分)", score: 6 }
        ],
        10: [
          { text: "A. 粗粮蔬菜为主 (0分)", score: 0 },
          { text: "B. 混合饮食 (1分)", score: 1 },
          { text: "C. 精细零食为主 (3分)", score: 3 }
        ],
        11: [
          { text: "A. 每次都漱口 (0分)", score: 0 },
          { text: "B. 仅早晚刷牙 (2分)", score: 2 },
          { text: "C. 从不漱口 (4分)", score: 4 }
        ],
        12: [
          { text: "A. 每6个月1次 (0分)", score: 0 },
          { text: "B. 每年1次 (1分)", score: 1 },
          { text: "C. 有症状才看 (3分)", score: 3 },
          { text: "D. 从未看过 (5分)", score: 5 }
        ],
        13: [
          { text: "A. 无龋齿 (0分)", score: 0 },
          { text: "B. 1-2颗未治 (2分)", score: 2 },
          { text: "C. ≥3颗未治 (4分)", score: 4 },
          { text: "D. 不清楚 (2分)", score: 2 }
        ],
        14: [
          { text: "A. 从不吸烟 (0分)", score: 0 },
          { text: "B. 偶尔吸烟 (2分)", score: 2 },
          { text: "C. 经常吸烟 (4分)", score: 4 }
        ],
        15: [
          { text: "A. 大专及以上 (0分)", score: 0 },
          { text: "B. 高中/中专 (1分)", score: 1 },
          { text: "C. 初中及以下 (3分)", score: 3 }
        ]
      },
      detections: null,
      submitting: false
    };
  },
   onLoad(options) {
    // --- 修改开始 ---
    // 从本地缓存读取检测结果，不再依赖 URL 传参
    try {
      const storageData = uni.getStorageSync('temp_detections');
      if (storageData) {
        this.detections = storageData;
        console.log('成功从缓存读取检测结果', this.detections);
        
        // 读取成功后，建议清除缓存，防止下次进入页面时读到旧数据（脏数据）
        // 如果用户返回上一页重新上传，这里清除是安全的
        uni.removeStorageSync('temp_detections');
      } else {
        console.warn('未在缓存中找到检测结果');
        uni.showToast({ title: '未获取到检测结果，请重新上传', icon: 'none', duration: 2000 });
        // 延迟返回上一页
        setTimeout(() => {
          uni.navigateBack();
        }, 2000);
      }
    } catch (e) {
      console.error('读取缓存失败', e);
      uni.showToast({ title: '数据读取异常', icon: 'none' });
    }
    // --- 修改结束 ---
  },
  methods: {
    // 获取当前选中项的文本显示
    getSelectedText(n) {
      const score = this.questionnaire['q' + n];
      if (score === null || score === undefined) return '请选择';
      const options = this.answerOptions[n];
      const selected = options.find(opt => opt.score === score);
      return selected ? selected.text : '请选择';
    },
    // 处理选项变更
    onAnswerChange(n, e) {
      // e.detail.value 是选中的索引
      const index = parseInt(e.detail.value);
      const options = this.answerOptions[n];
      if (options && options[index]) {
        // 存储的是 score，而不是 index
        this.$set(this.questionnaire, 'q' + n, options[index].score);
      }
    },
    submit() {
      if (!this.age) {
        uni.showToast({ title: '请输入年龄', icon: 'none' });
        return;
      }
      
      // 检查是否所有题目都已作答
      for (let i = 1; i <= 15; i++) {
        if (this.questionnaire['q' + i] === null || this.questionnaire['q' + i] === undefined) {
          uni.showToast({ title: `请完成第${i}题`, icon: 'none' });
          return;
        }
      }

      if (!this.detections) {
        uni.showToast({ title: '缺少检测结果', icon: 'none' });
        return;
      }

      this.submitting = true;
      uni.request({
        url: 'http://192.168.153.152:8080/assess',
        method: 'POST',
        data: {
          age: this.age,
          questionnaire: this.questionnaire,
          detections: this.detections
        },
        success: (res) => {
          if (res.statusCode === 200) {
            const data = res.data;
            if (data.success) {
               // 1. 将评估结果存入本地缓存
              uni.setStorageSync('temp_assessment_result', data);
      
              // 2. 跳转到结果页，不带参数
              uni.navigateTo({
                url: '/pages/result/result'
              });
            } else {
              uni.showToast({ title: data.message || '评估失败', icon: 'none' });
            }
          } else {
            uni.showToast({ title: '服务器异常', icon: 'none' });
          }
        },
        fail: (err) => {
          uni.showToast({ title: '网络请求失败', icon: 'none' });
          console.error(err);
        },
        complete: () => {
          this.submitting = false;
        }
      });
    }
  }
};
</script>

<style scoped>
.container {
  padding: 30rpx;
  background-color: #f8f8f8;
  min-height: 100vh;
}
.header {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
  margin-bottom: 30rpx;
  display: block;
  text-align: center;
}
.section-title {
  margin-top: 20rpx;
  margin-bottom: 10rpx;
  padding-left: 10rpx;
  border-left: 8rpx solid #007AFF;
}
.label {
  font-size: 30rpx;
  font-weight: bold;
  color: #555;
}
.field {
  background-color: #fff;
  padding: 20rpx;
  border-radius: 16rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 6rpx rgba(0,0,0,0.05);
}
.question-item {
  display: flex;
  flex-direction: column;
}
.question-text {
  font-size: 28rpx;
  color: #333;
  margin-bottom: 15rpx;
  line-height: 1.5;
}
.input-box {
  height: 80rpx;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  padding: 0 20rpx;
  font-size: 28rpx;
  background-color: #f9f9f9;
}
.picker {
  height: 80rpx;
  line-height: 80rpx;
  border: 1rpx solid #ddd;
  border-radius: 8rpx;
  padding: 0 20rpx;
  font-size: 28rpx;
  background-color: #fff;
  color: #333;
  display: flex;
  align-items: center;
}
.footer-btn {
  position: fixed;
  bottom: 0;
  left: 0;
  width: 100%;
  background-color: #fff;
  padding: 20rpx 30rpx;
  box-shadow: 0 -2rpx 10rpx rgba(0,0,0,0.05);
  box-sizing: border-box;
}
.submit-btn {
  width: 100%;
  background-color: #007AFF;
  color: #fff;
  border-radius: 50rpx;
  font-size: 32rpx;
  height: 90rpx;
  line-height: 90rpx;
}
</style>
