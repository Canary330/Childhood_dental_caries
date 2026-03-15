<template>
  <view class="container">
    <!-- 头部标题 -->
    <view class="header">
      <text class="title">🦷 口腔智能检测</text>
      <text class="sub-title">上传牙片 · 秒级识别</text>
    </view>

    <!-- 上传卡片 -->
    <view class="upload-card" @click="chooseImage" :style="{ borderColor: isDragover ? '#007AFF' : '#E9F0F9' }">
      <image v-if="imageUrl" :src="imageUrl" mode="aspectFill" class="preview-img"></image>
      <view v-else class="upload-placeholder">
        <text class="upload-icon">📸</text>
        <text class="upload-text">点击选择口腔图片</text>
        <text class="upload-hint">支持 JPG/PNG，单张</text>
      </view>
    </view>

    <!-- 上传按钮 & 状态 -->
    <view class="action-bar">
      <button type="primary" @click="uploadImage" :disabled="!imageUrl || uploading" :loading="uploading">
        {{ uploading ? '检测中...' : '开始检测' }}
      </button>
      <text v-if="errorMsg" class="error-text">{{ errorMsg }}</text>
      <!-- 只有当有结果时才显示填写问卷按钮 -->
      <button v-if="result" @click="gotoQuestionnaire" class="fill-btn">填写问卷</button>
    </view>

    <!-- 检测结果卡片（有数据才显示） -->
    <view v-if="result" class="result-section">
      <!-- 统计卡片 -->
      <view class="stats-grid">
        <view class="stat-item">
          <text class="stat-number">{{ result.teeth_count }}</text>
          <text class="stat-label">牙齿数量</text>
        </view>
        <view class="stat-item">
          <text class="stat-number">{{ result.caries_count }}</text>
          <text class="stat-label">龋齿</text>
        </view>
        <view class="stat-item">
          <text class="stat-number">{{ result.total_detections }}</text>
          <text class="stat-label">检测目标</text>
        </view>
      </view>

      <!-- 检测项列表标题 -->
      <view class="list-header">
        <text class="list-title">🔍 检测明细</text>
        <text class="file-name">📎 {{ result.image_name }}</text>
      </view>

      <!-- 检测项列表 -->
      <scroll-view scroll-y class="detection-list">
        <view v-for="(item, index) in result.detections" :key="index" class="detection-item">
          <view class="item-left">
            <view class="tag" :class="getClassColor(item.class_name)">
              {{ item.class_name }}
            </view>
            <view class="item-info">
              <text class="confidence">{{ (item.confidence * 100).toFixed(1) }}%</text>
              <text v-if="item.fdi_number" class="fdi">FDI: {{ item.fdi_number }}</text>
              <text v-if="item.tooth_type" class="tooth-type">{{ item.tooth_type === 'permanent' ? '恒牙' : '乳牙' }}</text>
            </view>
          </view>
          <view class="item-right">
            <text class="bbox">[{{ item.bbox.map(v => v.toFixed(0)).join(', ') }}]</text>
          </view>
        </view>
      </scroll-view>

      <!-- 检测时间/状态 -->
      <view class="result-footer">
        <text class="success-badge">✅ {{ result.message }}</text>
      </view>
    </view>

    <!-- 无结果时的占位提示 -->
    <view v-else-if="!uploading" class="empty-state">
      <text class="empty-icon">🦷</text>
      <text class="empty-text">点击上方卡片选择牙片</text>
      <text class="empty-hint">我们会对牙齿位置、龋齿等进行智能识别</text>
    </view>
  </view>
</template>

<script>
export default {
  data() {
    return {
      imageUrl: '',           // 选择的图片本地路径
      file: null,            // 文件对象（用于上传）
      uploading: false,      // 是否正在上传
      result: null,         // 后端返回的检测结果
      errorMsg: '',         // 错误提示
      isDragover: false,    // 拖拽状态（预留）
    };
  },
  methods: {
    // 选择图片
    chooseImage() {
      uni.chooseImage({
        count: 1,
        sizeType: ['compressed'],
        sourceType: ['album', 'camera'],
        success: (res) => {
          this.imageUrl = res.tempFilePaths[0];
          this.file = res.tempFiles[0];
          this.result = null;   // 清空上次结果
          this.errorMsg = '';
        },
        fail: (err) => {
          console.error('选择图片失败', err);
        }
      });
    },

    // 上传图片进行检测
    uploadImage() {
      if (!this.file) return;

      this.uploading = true;
      this.errorMsg = '';

      uni.uploadFile({
        url: 'http://192.168.153.152:8080/upload',  // 后端地址
        filePath: this.imageUrl,
        name: 'file',
        success: (res) => {
          if (res.statusCode === 200) {
            try {
              const data = JSON.parse(res.data);
              if (data.success) {
                this.result = data;   // 保存完整返回结果
                // 成功后，自动将检测结果存入缓存，方便问卷页面读取
                try {
                  uni.setStorageSync('temp_detections', data.detections);
                  console.log('检测结果已存入缓存');
                } catch (e) {
                  console.error('存储检测结果失败', e);
                  uni.showToast({ title: '数据存储失败', icon: 'none' });
                }
              } else {
                this.errorMsg = data.message || '检测失败';
              }
            } catch (e) {
              console.error('解析返回数据失败', e);
              this.errorMsg = '服务器返回数据格式错误';
            }
          } else {
            this.errorMsg = `服务器响应异常 (${res.statusCode})`;
          }
        },
        fail: (err) => {
          console.error('上传失败', err);
          this.errorMsg = '网络错误，请检查网络连接或后端服务';
        },
        complete: () => {
          this.uploading = false;
        }
      });
    },

    // 跳转到问卷页面
    gotoQuestionnaire() {
      if (!this.result) return;
      // 修改：不再通过 URL 传递 data，直接跳转
      // 因为数据已经在 uploadImage 成功回调中存入了 'temp_detections'
      uni.navigateTo({
        url: '/pages/questionnaire/questionnaire'
      });
    },

    // 根据类别名称返回对应的标签颜色类名
    getClassColor(className) {
      const map = {
        'oc': 'tag-purple',
        '1st': 'tag-blue',
        '2nd': 'tag-blue',
        '3rd': 'tag-blue',
        '4th': 'tag-blue',
        '5th': 'tag-blue',
        '6th': 'tag-blue',
        '7th': 'tag-blue',
        'caries': 'tag-red',
        'space': 'tag-gray',
      };
      return map[className] || 'tag-default';
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
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
}

/* 头部 */
.header {
  margin-bottom: 40rpx;
  padding-top: 20rpx;
}
.title {
  font-size: 48rpx;
  font-weight: 700;
  color: #1A3B4E;
  display: block;
  line-height: 1.3;
}
.sub-title {
  font-size: 28rpx;
  color: #6C8B9B;
  margin-top: 8rpx;
  display: block;
  font-weight: 400;
}

/* 上传卡片 */
.upload-card {
  width: 100%;
  height: 380rpx;
  background: white;
  border-radius: 32rpx;
  border: 2rpx dashed #D0E0E8;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  box-shadow: 0 8rpx 24rpx rgba(0, 100, 150, 0.08);
  transition: all 0.2s ease;
  margin-bottom: 30rpx;
}
.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.upload-icon {
  font-size: 72rpx;
  margin-bottom: 16rpx;
  opacity: 0.7;
}
.upload-text {
  font-size: 32rpx;
  color: #2C5F73;
  font-weight: 500;
}
.upload-hint {
  font-size: 24rpx;
  color: #8AA9B6;
  margin-top: 12rpx;
}
.preview-img {
  width: 100%;
  height: 100%;
}

/* 操作栏 */
.action-bar {
  margin-bottom: 40rpx;
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}
button {
  width: 100%;
  background: linear-gradient(145deg, #1F8A9E, #116B7C);
  color: white;
  border-radius: 60rpx;
  height: 90rpx;
  font-size: 32rpx;
  font-weight: 500;
  box-shadow: 0 10rpx 20rpx rgba(17, 107, 124, 0.2);
  border: none;
}
button[disabled] {
  opacity: 0.5;
  box-shadow: none;
}
/* 填充按钮样式（用于次要操作） */
.fill-btn {
  background: white;
  color: #1F8A9E;
  border: 2rpx solid #1F8A9E;
  box-shadow: none;
}

.error-text {
  display: block;
  text-align: center;
  color: #D92B4B;
  font-size: 26rpx;
  margin-top: 10rpx;
}

/* 结果区域 */
.result-section {
  background: white;
  border-radius: 36rpx;
  padding: 40rpx 30rpx;
  box-shadow: 0 12rpx 32rpx rgba(0, 60, 90, 0.06);
  margin-top: 20rpx;
}

/* 统计卡片（三列） */
.stats-grid {
  display: flex;
  justify-content: space-around;
  margin-bottom: 50rpx;
}
.stat-item {
  text-align: center;
  flex: 1;
}
.stat-number {
  font-size: 56rpx;
  font-weight: 800;
  color: #1A3B4E;
  line-height: 1.2;
  display: block;
}
.stat-label {
  font-size: 26rpx;
  color: #6C8B9B;
  display: block;
  margin-top: 8rpx;
}

/* 列表头部 */
.list-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 24rpx;
  border-bottom: 2rpx solid #E9F0F4;
  padding-bottom: 24rpx;
}
.list-title {
  font-size: 34rpx;
  font-weight: 600;
  color: #1A3B4E;
}
.file-name {
  font-size: 24rpx;
  color: #6C8B9B;
  max-width: 260rpx;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 检测项列表滚动 */
.detection-list {
  max-height: 600rpx;
  overflow-y: auto;
}
.detection-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24rpx 0;
  border-bottom: 2rpx solid #F0F6F9;
}
.item-left {
  display: flex;
  align-items: center;
  flex: 1;
}
.tag {
  font-size: 24rpx;
  font-weight: 600;
  padding: 10rpx 24rpx;
  border-radius: 40rpx;
  margin-right: 20rpx;
  color: white;
  white-space: nowrap;
}
.tag-purple { background: #735CDD; }
.tag-blue { background: #2D9CDB; }
.tag-red { background: #EB5757; }
.tag-gray { background: #828282; }
.tag-default { background: #6C8B9B; }

.item-info {
  display: flex;
  flex-direction: column;
}
.confidence {
  font-size: 28rpx;
  font-weight: 600;
  color: #1F2E35;
}
.fdi, .tooth-type {
  font-size: 22rpx;
  color: #5C7A8A;
  margin-top: 6rpx;
}
.item-right {
  margin-left: 20rpx;
}
.bbox {
  font-size: 22rpx;
  color: #7F9FAA;
  background: #F1F7FA;
  padding: 8rpx 16rpx;
  border-radius: 24rpx;
  white-space: nowrap;
}

/* 结果底部 */
.result-footer {
  margin-top: 40rpx;
  padding-top: 24rpx;
  border-top: 2rpx solid #E9F0F4;
}
.success-badge {
  font-size: 28rpx;
  color: #1F8A9E;
  font-weight: 500;
}

/* 空状态 */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 100rpx 0;
}
.empty-icon {
  font-size: 100rpx;
  opacity: 0.3;
  margin-bottom: 30rpx;
}
.empty-text {
  font-size: 32rpx;
  color: #2C5F73;
  font-weight: 500;
}
.empty-hint {
  font-size: 26rpx;
  color: #8AA9B6;
  margin-top: 16rpx;
}
</style>
