<template>
  <view class="container">
    <!-- 头部 -->
    <view class="header">
      <text class="title">📊 评估结果报告</text>
      <text class="sub-title">基于问卷与智能检测结果</text>
    </view>

    <!-- 结果卡片 -->
    <view v-if="data.category" class="result-card">
      <!-- 风险等级大标题 -->
      <view class="risk-badge" :class="getRiskClass(data.category)">
        <text class="risk-icon">{{ getRiskIcon(data.category) }}</text>
        <text class="risk-text">{{ data.category }}</text>
      </view>

      <!-- 分数详情 -->
      <view class="score-section">
        <view class="score-row">
          <text class="score-label">问卷原始得分</text>
          <text class="score-value">{{ data.score }} 分</text>
        </view>
        <view class="divider"></view>
        <view class="score-row">
          <text class="score-label">AI 调整后得分</text>
          <text class="score-value highlight">{{ data.adjusted_score }} 分</text>
        </view>
      </view>

      <!-- 规则触发详情 -->
      <view v-if="data.details && data.details.length" class="rules-section">
        <view class="section-title">
          <text class="title-text">⚠️ 触发的特殊规则</text>
        </view>
        <view class="rules-list">
          <view v-for="(r, i) in data.details" :key="i" class="rule-item">
            <view class="rule-header">
              <text class="rule-code">{{ r.rule }}</text>
            </view>
            <text class="rule-msg">{{ r.message }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 空状态或加载中 -->
    <view v-else class="empty-state">
      <text class="loading-text">正在加载结果...</text>
    </view>

    <!-- 底部按钮 -->
    <view class="footer">
      <button type="primary" @click="gotoHome" class="home-btn">返回首页</button>
    </view>
  </view>
</template>

<script>
export default {
  data() {
    return {
      data: {}
    };
  },
  onLoad() {
    // 页面加载时尝试读取数据
    this.loadResultData();
  },
  onShow() {
    // 如果从其他页面返回，可能需要重新加载数据（视具体业务逻辑而定）
    // 这里为了简单，仅在 onLoad 处理，如果数据为空则跳转
    if (!this.data.category) {
      this.loadResultData();
    }
  },
  methods: {
    loadResultData() {
      try {
        const storageData = uni.getStorageSync('temp_assessment_result');
        if (storageData) {
          this.data = storageData;
          console.log('读取评估结果成功', this.data);
          
          // 读取后立即清除缓存，防止脏数据
          uni.removeStorageSync('temp_assessment_result');
        } else {
          console.warn('未找到评估结果数据');
          uni.showToast({ title: '未获取到评估结果', icon: 'none' });
          // 延迟跳转回首页
          setTimeout(() => {
            uni.reLaunch({ url: '/pages/index/index' });
          }, 1500);
        }
      } catch (e) {
        console.error('读取缓存失败', e);
        uni.showToast({ title: '数据读取异常', icon: 'none' });
      }
    },
    gotoHome() {
      uni.reLaunch({ url: '/pages/index/index' });
    },
    // 辅助方法：根据风险等级返回样式类名
    getRiskClass(category) {
      if (category.includes('低')) return 'risk-low';
      if (category.includes('中')) return 'risk-medium';
      if (category.includes('高')) return 'risk-high';
      return 'risk-default';
    },
    // 辅助方法：根据风险等级返回图标
    getRiskIcon(category) {
      if (category.includes('低')) return '🛡️';
      if (category.includes('中')) return '⚠️';
      if (category.includes('高')) return '🔥';
      return '📊';
    }
  }
};
</script>

<style scoped>
.container {
  min-height: 100vh;
  background: linear-gradient(145deg, #F8FCFE 0%, #F0F7FA 100%);
  padding: 30rpx;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
}

/* 头部 */
.header {
  margin-bottom: 40rpx;
  padding-top: 40rpx;
  text-align: center;
}
.title {
  font-size: 44rpx;
  font-weight: 700;
  color: #1A3B4E;
  display: block;
  margin-bottom: 10rpx;
}
.sub-title {
  font-size: 26rpx;
  color: #6C8B9B;
}

/* 结果卡片 */
.result-card {
  background: white;
  border-radius: 32rpx;
  padding: 40rpx;
  box-shadow: 0 10rpx 30rpx rgba(0, 60, 90, 0.06);
  margin-bottom: 30rpx;
}

/* 风险等级徽章 */
.risk-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 30rpx;
  border-radius: 24rpx;
  margin-bottom: 40rpx;
  background-color: #f0f0f0;
}
.risk-low { background-color: #E6FFFA; color: #2C7A7B; }
.risk-medium { background-color: #FFFFF0; color: #B7791F; }
.risk-high { background-color: #FFF5F5; color: #C53030; }
.risk-icon { font-size: 48rpx; margin-right: 16rpx; }
.risk-text { font-size: 36rpx; font-weight: 700; }

/* 分数区域 */
.score-section {
  padding: 20rpx 0;
}
.score-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20rpx 0;
}
.score-label {
  font-size: 30rpx;
  color: #555;
}
.score-value {
  font-size: 36rpx;
  font-weight: 600;
  color: #333;
}
.score-value.highlight {
  color: #007AFF;
  font-size: 40rpx;
}
.divider {
  height: 1rpx;
  background-color: #eee;
  margin: 10rpx 0;
}

/* 规则区域 */
.rules-section {
  margin-top: 50rpx;
  padding-top: 30rpx;
  border-top: 2rpx dashed #eee;
}
.section-title {
  margin-bottom: 20rpx;
}
.title-text {
  font-size: 30rpx;
  font-weight: 600;
  color: #333;
}
.rules-list {
  background-color: #FAFAFA;
  border-radius: 16rpx;
  padding: 20rpx;
}
.rule-item {
  background: white;
  padding: 20rpx;
  border-radius: 12rpx;
  margin-bottom: 16rpx;
  border-left: 6rpx solid #FFD700;
}
.rule-item:last-child { margin-bottom: 0; }
.rule-header {
  margin-bottom: 8rpx;
}
.rule-code {
  font-size: 24rpx;
  font-weight: 700;
  color: #666;
  background: #eee;
  padding: 4rpx 12rpx;
  border-radius: 8rpx;
}
.rule-msg {
  font-size: 28rpx;
  color: #444;
  line-height: 1.5;
}

/* 底部按钮 */
.footer {
  margin-top: auto;
  padding: 20rpx 0;
}
.home-btn {
  width: 100%;
  background: linear-gradient(145deg, #1F8A9E, #116B7C);
  color: white;
  border-radius: 60rpx;
  height: 90rpx;
  line-height: 90rpx;
  font-size: 32rpx;
  border: none;
}

/* 空状态 */
.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
.loading-text {
  font-size: 28rpx;
  color: #999;
}
</style>
