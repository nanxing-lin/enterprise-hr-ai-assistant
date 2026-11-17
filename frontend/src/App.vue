<template>
  <el-container class="layout-container">
    <!-- 左侧菜单 -->
    <el-aside width="240px" class="sidebar">
      <div class="logo-area">
        <div class="logo-icon">✦</div>
        <div class="logo-text">ChatBI Pro</div>
      </div>
      
      <!-- 核心：绑定点击事件，切换视图 -->
      <el-menu :default-active="currentView" class="custom-menu" @select="handleMenuSelect">
        <el-menu-item index="upload">
          <el-icon><UploadFilled /></el-icon>
          <span>上传数据</span>
        </el-menu-item>
        <el-menu-item index="chat">
          <el-icon><ChatDotRound /></el-icon>
          <span>AI 智能提问</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <!-- 右侧主内容 -->
    <el-container class="main-container">
      <el-header class="top-header">
        <div class="breadcrumb">工作台 / <strong>{{ currentView === 'upload' ? '数据导入' : '智能问答' }}</strong></div>
      </el-header>

      <el-main class="content-area">
        
        <!-- ================= 视图一：上传界面 ================= -->
        <div v-show="currentView === 'upload'" class="view-section">
          <div class="welcome-section">
            <h1 class="title">数据导入</h1>
            <p class="subtitle">请上传你的 Excel 或 CSV 文件，系统将自动解析。</p>
          </div>

          <div class="upload-card-wrapper">
            <el-upload class="advanced-uploader" drag :http-request="customUpload" multiple>
              <div class="upload-inner">
                <el-icon class="upload-icon"><UploadFilled /></el-icon>
                <div class="upload-text">将数据文件拖拽至此，或 <span class="highlight">点击浏览</span></div>
              </div>
            </el-upload>
          </div>
          
          <!-- 这个按钮现在是真的了：点击后跳转到 AI 视图 -->
          <el-button type="primary" size="large" class="action-btn" @click="goToChat" :disabled="!hasData">
            {{ hasData ? '数据已就绪，去提问 →' : '请先上传数据' }}
          </el-button>
        </div>

        <!-- ================= 视图二：AI 提问界面 ================= -->
        <div v-show="currentView === 'chat'" class="view-section chat-view">
          <div class="welcome-section">
            <h1 class="title">AI 智能问答</h1>
            <p class="subtitle">你可以用大白话向数据提问，例如：“这组数据里销售额最高的是哪个？”</p>
          </div>

          <!-- 聊天记录区 -->
          <div class="chat-history" ref="chatHistoryRef">
            <div v-for="(msg, index) in chatMessages" :key="index" :class="['message', msg.role]">
              <div class="bubble">{{ msg.content }}</div>
            </div>
            <!-- AI 思考时的加载动画 -->
            <div v-if="isThinking" class="message ai">
              <div class="bubble loading">AI 正在查阅数据并思考中...</div>
            </div>
          </div>

          <!-- 提问输入框 -->
          <div class="chat-input-box">
            <el-input 
              v-model="question" 
              placeholder="请输入你想问的问题..." 
              @keyup.enter="askAI"
              size="large"
              :disabled="!hasData"
            />
            <el-button type="primary" size="large" @click="askAI" :loading="isThinking" :disabled="!hasData" class="send-btn">
              发送
            </el-button>
          </div>
        </div>

      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { UploadFilled, ChatDotRound } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

// 状态控制
const currentView = ref('upload') // 当前显示的视图：'upload' 或 'chat'
const hasData = ref(false) // 是否已经成功上传了数据
const question = ref('')
const chatMessages = ref([])
const isThinking = ref(false)
const chatHistoryRef = ref(null)

// 菜单点击切换
const handleMenuSelect = (index) => {
  currentView.value = index;
  if(index === 'chat' && !hasData.value){
      ElMessage.warning('请先在左侧上传数据文件！');
  }
}

// 上传成功后，自动跳转到聊天界面
const goToChat = () => {
  if (hasData.value) {
    currentView.value = 'chat';
  }
}

// 上传文件逻辑
const customUpload = async (options) => {
  const file = options.file;
  if (!file.name.endsWith('.xlsx') && !file.name.endsWith('.csv')) {
    ElMessage.error('仅支持 Excel (.xlsx) 或 CSV (.csv) 格式文件！');
    return;
  }

  ElMessage.info(`正在解析文件：${file.name}...`);
  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await fetch("http://127.0.0.1:8000/upload", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if(response.ok) {
        ElMessage.success(`✅ ${data.message}`);
        hasData.value = true;
        chatMessages.value = [{ role: 'ai', content: `数据加载完毕！我已经记住了这份数据的特征。你可以开始向我提问了。` }];
    } else {
        ElMessage.error(`解析失败：${data.message}`);
    }
  } catch (error) {
    ElMessage.error("上传失败，请确保后端已启动！");
  }
};

// 向 AI 提问逻辑
const askAI = async () => {
  if (!question.value.trim()) return;
  if (!hasData.value) return ElMessage.warning("请先上传数据！");
  
  // 1. 显示用户问题
  chatMessages.value.push({ role: 'user', content: question.value });
  const currentQ = question.value;
  question.value = '';
  isThinking.value = true;
  
  scrollToBottom();

  try {
    // 2. 发请求给后端
    const response = await fetch("http://127.0.0.1:8000/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: currentQ })
    });
    const data = await response.json();
    
    // 3. 显示 AI 回答
    chatMessages.value.push({ role: 'ai', content: data.answer });
  } catch (error) {
    chatMessages.value.push({ role: 'ai', content: "网络错误，无法连接 AI 服务。" });
  } finally {
    isThinking.value = false;
    scrollToBottom();
  }
}

// 让聊天框自动滚动到最底部
const scrollToBottom = () => {
  nextTick(() => {
    if (chatHistoryRef.value) {
      chatHistoryRef.value.scrollTop = chatHistoryRef.value.scrollHeight;
    }
  })
}
</script>

<style scoped>
/* 全局布局 */
.layout-container { height: 100vh; background-color: #f0f2f5; }

/* 左侧侧边栏 */
.sidebar { background-color: #111827; display: flex; flex-direction: column; color: #fff; }
.logo-area { height: 70px; display: flex; align-items: center; padding: 0 24px; border-bottom: 1px solid rgba(255,255,255,0.05); }
.logo-icon { width: 32px; height: 32px; background: linear-gradient(135deg, #6366f1, #3b82f6); border-radius: 8px; display: flex; justify-content: center; align-items: center; font-size: 18px; margin-right: 12px; }
.logo-text { font-size: 20px; font-weight: 600; }
.custom-menu { border-right: none; background-color: transparent; padding: 20px 10px; flex: 1;}
:deep(.el-menu-item) { color: #9ca3af; border-radius: 8px; margin-bottom: 8px; }
:deep(.el-menu-item:hover) { background: rgba(255,255,255,0.05); color: #fff; }
:deep(.el-menu-item.is-active) { background: rgba(99, 102, 241, 0.2); color: #818cf8; border-left: 3px solid #6366f1; }

/* 右侧主体 */
.main-container { display: flex; flex-direction: column; }
.top-header { height: 70px; background: #fff; display: flex; align-items: center; padding: 0 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.02); }
.content-area { padding: 30px; max-width: 1000px; margin: 0 auto; width: 100%; }

/* 通用标题 */
.welcome-section { margin-bottom: 30px; }
.title { font-size: 28px; color: #111827; margin-bottom: 8px; }
.subtitle { color: #6b7280; }

/* 上传区样式 */
.upload-card-wrapper { background: #fff; border-radius: 16px; padding: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.03); margin-bottom: 30px; }
:deep(.el-upload-dragger) { background-color: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px; padding: 40px 0; transition: all 0.3s; }
:deep(.el-upload-dragger:hover) { border-color: #6366f1; background-color: #eef2ff; }
.upload-inner { display: flex; flex-direction: column; align-items: center; }
.upload-icon { font-size: 48px; color: #6366f1; margin-bottom: 16px; }
.highlight { color: #6366f1; text-decoration: underline; cursor: pointer; }
.action-btn { border-radius: 8px; background: #6366f1; border-color: #6366f1; padding: 12px 30px; font-weight: 500; }

/* 聊天区样式 */
.chat-view { display: flex; flex-direction: column; height: calc(100vh - 130px); }
.chat-history { flex: 1; background: #fff; border-radius: 12px; padding: 20px; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; box-shadow: 0 4px 12px rgba(0,0,0,0.02); margin-bottom: 20px;}
.message { display: flex; }
.message.user { justify-content: flex-end; }
.bubble { padding: 12px 18px; border-radius: 12px; max-width: 75%; line-height: 1.6; font-size: 15px; }
.message.user .bubble { background: #6366f1; color: #fff; border-bottom-right-radius: 2px; }
.message.ai .bubble { background: #f3f4f6; color: #374151; border-bottom-left-radius: 2px; }
.loading { color: #9ca3af; font-style: italic; }
.chat-input-box { display: flex; gap: 12px; }
.send-btn { background: #6366f1; border-color: #6366f1; width: 120px;}
</style>