<template>
  <div class="home-container">
    <el-container>
      <!-- 侧边栏 - 保持原有功能不变 -->
      <el-aside width="250px" class="sidebar">
        <div class="user-info">
          <el-avatar :size="50" :src="userAvatar" />
          <span class="username">{{ authStore.user?.username }}</span>
          <el-button type="text" @click="authStore.logout" class="logout-btn">
            退出登录
          </el-button>
        </div>

        <el-button type="primary" @click="newConversation" class="new-chat-btn">
          <el-icon><plus /></el-icon>
          新对话
        </el-button>

        <el-menu :default-active="activeConversation" class="conversation-list">
          <el-menu-item
            v-for="(conv, index) in conversations"
            :key="index"
            :index="String(index)"
            @click="selectConversation(index)"
          >
            <span>{{ conv.title }}</span>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 主内容区 - 修改为故事风格 -->
      <el-main class="story-container">
        <div class="story-welcome">
          <h2>儿童故事乐园</h2>
          <p>
            <strong
              >你好！我是故事精灵，可以为你创作有趣的人类故事并进行情感分析。你想听什么故事呢？</strong
            >
          </p>
        </div>

        <!-- 保留原有的消息列表，但初始隐藏 -->
        <div
          class="message-list"
          ref="messageList"
          v-show="currentMessages.length > 0"
        >
          <div
            v-for="(msg, index) in currentMessages"
            :key="index"
            :class="['message-item', msg.role]"
          >
            <div class="message-content">
              <div class="message-avatar">
                <el-avatar
                  :size="40"
                  :src="msg.role === 'user' ? userAvatar : botAvatar"
                />
              </div>
              <div class="message-text">
                <div class="message-meta">
                  <span class="message-role">{{
                    msg.role === "user" ? "你" : "AI助手"
                  }}</span>
                  <span class="message-time">{{ msg.timestamp }}</span>
                </div>
                <div class="message-body">{{ msg.content }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区域保持不变 -->
        <div class="input-area">
          <el-input
            v-model="userInput"
            type="textarea"
            :rows="3"
            placeholder="输入你想听的故事主题..."
            @keyup.enter.native="sendMessage"
          />
          <el-button
            type="primary"
            @click="sendMessage"
            :loading="isSending"
            class="send-btn"
          >
            发送
          </el-button>

          <!-- 将热门主题移动到输入框下方 -->
          <div class="popular-themes">
            <h4>热门故事主题：</h4>
            <ul>
              <li @click="isThemeClick = true; userInput = '勇敢的小兔子'; sendMessage()">
                <strong>勇敢的小兔子</strong>
              </li>
              <li @click="isThemeClick = true; userInput = '友谊的力量'; sendMessage()">
                <strong>友谊的力量</strong>
              </li>
              <li @click="isThemeClick = true; userInput = '森林冒险'; sendMessage()">
                <strong>森林冒险</strong>
              </li>
              <li @click="isThemeClick = true; userInput = '超级英雄'; sendMessage()">
                <strong>超级英雄</strong>
              </li>
            </ul>
          </div>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
// 保持原有的script部分完全不变
import { ref, computed, onMounted, nextTick } from "vue";
import { useAuthStore } from "../stores/auth";
import { Plus } from "@element-plus/icons-vue";
import axios from "axios";
import { ElMessage } from "element-plus";

const authStore = useAuthStore();

const userInput = ref("");
const isSending = ref(false);
const conversations = ref([]);
const currentMessages = ref([]);
const activeConversation = ref(0);
const messageList = ref(null);
const isThemeClick = ref(false);

const userAvatar = computed(
  () =>
    `https://api.dicebear.com/7.x/initials/svg?seed=${authStore.user?.username}`
);
const botAvatar = "https://api.dicebear.com/7.x/bottts/svg?seed=AI";

// 初始化对话
const initConversations = () => {
  const saved = localStorage.getItem(`conversations_${authStore.user?.id}`);
  if (saved) {
    conversations.value = JSON.parse(saved);
    if (conversations.value.length > 0) {
      currentMessages.value = conversations.value[0].messages || [];
    }
  } else {
    newConversation();
  }
};

// 创建新对话
const newConversation = () => {
  const newConv = {
    title: `新对话 ${conversations.value.length + 1}`,
    messages: [],
    createdAt: new Date().toLocaleString(),
  };
  conversations.value.unshift(newConv);
  activeConversation.value = 0;
  currentMessages.value = [];
  saveConversations();
};

// 选择对话
const selectConversation = (index) => {
  activeConversation.value = index;
  currentMessages.value = conversations.value[index].messages;
};

// 发送消息
const sendMessage = async () => {
  if (!userInput.value.trim()) return;

  const userMsg = {
    role: "user",
    content: userInput.value,
    timestamp: new Date().toLocaleTimeString(),
  };

  currentMessages.value.push(userMsg);
  saveConversations();
  scrollToBottom();

  try {
    isSending.value = true;
    const response = await axios.post(
      "http://localhost:5000/api/ask",
      {
        question: userInput.value,
      },
      {
        headers: {
          Authorization: `Bearer ${authStore.token}`,
        },
      }
    );

    const aiMsg = {
      role: "ai",
      content: response.data.answer,
      timestamp: new Date().toLocaleTimeString(),
    };
    currentMessages.value.push(aiMsg);
    saveConversations();
    scrollToBottom();
  } catch (error) {
    ElMessage.error("发送消息失败: " + error.message);
  } finally {
    if (!isThemeClick.value) {
      userInput.value = "";
    }
    isSending.value = false;
    isThemeClick.value = false;
  }
};

// 保存对话
const saveConversations = () => {
  conversations.value[activeConversation.value].messages =
    currentMessages.value;
  localStorage.setItem(
    `conversations_${authStore.user?.id}`,
    JSON.stringify(conversations.value)
  );
};

// 滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messageList.value) {
      messageList.value.scrollTop = messageList.value.scrollHeight;
    }
  });
};

onMounted(() => {
  initConversations();
});
</script>

<style scoped>
.home-container {
  height: 100vh;
  display: flex;
  background-color: #f9f9f9;
}

.sidebar {
  background: linear-gradient(135deg, #6c5ce7 0%, #a29bfe 100%);
  color: white;
  height: 100vh;
  padding: 20px;
  position: relative;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
}

.user-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 20px;
  padding: 15px;
  background-color: rgba(255, 255, 255, 0.15);
  border-radius: 10px;
}

.username {
  margin: 10px 0;
  font-weight: bold;
  color: white;
}

.logout-btn {
  color: white;
  opacity: 0.8;
}

.new-chat-btn {
  width: 100%;
  margin-bottom: 20px;
  background: white;
  color: #6c5ce7;
  border: none;
  font-weight: bold;
}

.conversation-list {
  border-right: none;
  background: transparent;
}

.conversation-list :deep(.el-menu-item) {
  color: white;
  margin-bottom: 5px;
  border-radius: 8px;
}

.conversation-list :deep(.el-menu-item.is-active) {
  background-color: rgba(255, 255, 255, 0.3);
}

/* 新的故事风格样式 */
.story-container {
  padding: 30px;
  background-color: white;
  height: 100vh;
  overflow-y: auto;
  background-image: url("https://img.freepik.com/free-vector/hand-painted-watercolor-pastel-sky-background_23-2148902771.jpg");
  background-size: cover;
  background-position: center;
}

.story-header {
  text-align: center;
  margin-bottom: 40px;
  padding: 20px;
  background-color: rgba(255, 255, 255, 0.8);
  border-radius: 15px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.story-header h1 {
  color: #6c5ce7;
  font-size: 2.5rem;
  margin-bottom: 15px;
  font-family: "Comic Sans MS", cursive, sans-serif;
}

.story-categories h2,
.story-categories h3 {
  color: #333;
  margin: 5px 0;
}

.story-categories h2 {
  font-size: 1.8rem;
  color: #e84393;
}

.story-categories h3 {
  font-size: 1.4rem;
  color: #0984e3;
}

.story-welcome {
  background-color: rgba(255, 255, 255, 0.85);
  padding: 30px;
  border-radius: 15px;
  margin-bottom: 30px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.story-welcome h2 {
  color: #6c5ce7;
  font-size: 2rem;
  margin-bottom: 15px;
  text-align: center;
}

.story-welcome p {
  font-size: 1.1rem;
  line-height: 1.6;
  color: #333;
  margin-bottom: 15px;
}

.popular-themes {
  margin-top: 15px;
}

.popular-themes h4 {
  font-size: 1rem;
  color: #6c5ce7;
  margin-bottom: 8px;
}

.popular-themes ul {
  list-style-type: none;
  padding: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.popular-themes li {
  font-size: 0.9rem;
  padding: 4px 10px;
  margin: 0;
  background-color: rgba(108, 92, 231, 0.1);
  border-radius: 6px;
  color: #6c5ce7;
  cursor: pointer;
  transition: all 0.2s;
}

.popular-themes li:hover {
  background-color: rgba(108, 92, 231, 0.2);
  transform: translateY(-2px);
}

/* 保留原有的消息样式 */
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background-color: rgba(255, 255, 255, 0.9);
  border-radius: 15px;
  margin-bottom: 20px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.message-item {
  margin-bottom: 20px;
}

.message-content {
  display: flex;
  max-width: 80%;
  margin: 0 auto;
}

.user .message-content {
  flex-direction: row-reverse;
}

.message-avatar {
  margin: 0 15px;
}

.message-text {
  flex: 1;
}

.message-meta {
  font-size: 12px;
  color: #666;
  margin-bottom: 5px;
}

.message-body {
  background: white;
  padding: 12px 18px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.user .message-body {
  background: linear-gradient(135deg, #6c5ce7 0%, #a29bfe 100%);
  color: white;
}

.input-area {
  padding: 20px;
  background-color: rgba(255, 255, 255, 0.9);
  border-radius: 15px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

.send-btn {
  margin-top: 10px;
  background: linear-gradient(135deg, #00b894 0%, #55efc4 100%);
  color: white;
  border: none;
}
</style>
