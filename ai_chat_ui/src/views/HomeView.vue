<template>
  <div class="home-container">
    <el-container>
      <!-- 侧边栏 -->
      <el-aside width="250px" class="sidebar">
        <div class="user-info">
          <el-avatar :size="50" :src="userAvatar" />
          <span class="username">{{ authStore.user?.username }}</span>
          <el-button type="text" @click="authStore.logout" class="logout-btn"
            >退出登录</el-button
          >
        </div>

        <el-button type="primary" @click="newConversation" class="new-chat-btn">
          <el-icon><Plus /></el-icon>新对话
        </el-button>

        <el-menu :default-active="activeConversation" class="conversation-list">
          <el-menu-item
            v-for="(conv, index) in conversations"
            :key="index"
            :index="String(index)"
            @click="selectConversation(index)"
          >
            <div
              style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                width: 100%;
              "
            >
              <span>{{ conv.title }}</span>
              <div style="display: flex; gap: 5px">
                <el-button
                  type="text"
                  :icon="Edit"
                  @click.stop="renameConversation(index)"
                  style="color: white"
                  circle
                  size="small"
                />
                <el-button
                  type="text"
                  :icon="Delete"
                  @click.stop="deleteConversation(index)"
                  style="color: white"
                  circle
                  size="small"
                />
              </div>
            </div>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <!-- 主内容区 -->
      <el-main class="story-container">
        <div class="story-welcome">
          <h2>童话故事王国</h2>
          <p><strong>你好！我是故事精灵，可以为你讲故事并分析情感~</strong></p>
          <el-button
            type="primary"
            @click="router.push('/sentiment-analysis')"
            class="sentiment-btn"
          >
            <el-icon><DataAnalysis /></el-icon>查看情感分析
          </el-button>
        </div>

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
                    msg.role === "user" ? "你" : "故事精灵"
                  }}</span>
                  <span class="message-time">{{ msg.timestamp }}</span>
                </div>
                <div class="message-body">{{ msg.content }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区域 - 重点美化部分 -->
        <div class="input-area">
          <!-- 热门童话主题区域 -->
          <div class="popular-themes">
            <h3>
              <el-icon><StarFilled /></el-icon> 热门童话主题
            </h3>
            <div class="theme-tags">
              <el-tag
                v-for="(theme, index) in popularThemes"
                :key="index"
                @click="selectTheme(theme)"
                class="theme-tag"
                effect="light"
              >
                {{ theme }}
              </el-tag>
            </div>
          </div>

          <div class="input-container">
            <el-input
              v-model="storyInput"
              placeholder="请输入你想听的故事内容..."
              @keyup.enter="sendStoryInput"
              clearable
              class="story-input"
            >
              <template #prefix>
                <el-icon><MagicStick /></el-icon>
              </template>
            </el-input>
            <el-button
              type="primary"
              @click="sendStoryInput"
              :loading="isSending"
              class="send-btn"
            >
              <el-icon><Promotion /></el-icon>发送
            </el-button>
          </div>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import axios from "axios";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  Plus,
  Delete,
  Edit,
  DataAnalysis,
  StarFilled,
  MagicStick,
  Promotion,
} from "@element-plus/icons-vue"; // 使用存在的图标

const router = useRouter();
const authStore = useAuthStore();

const storyInput = ref("");
const isSending = ref(false);
const isAnalyzing = ref(false);

const conversations = ref([]);
const currentMessages = ref([]);
const activeConversation = ref(0);
const messageList = ref(null);

// 热门童话主题
const popularThemes = ref([
  "小红帽",
  "三只小猪",
  "灰姑娘",
  "白雪公主",
  "青蛙王子",
  "睡美人",
  "阿拉丁神灯",
  "小美人鱼",
  "丑小鸭",
  "皇帝的新装",
]);

const userAvatar = computed(
  () =>
    `https://api.dicebear.com/7.x/initials/svg?seed=${authStore.user?.username}`
);
const botAvatar = "https://api.dicebear.com/7.x/bottts/svg?seed=AI";

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

const selectConversation = (index) => {
  activeConversation.value = index;
  currentMessages.value = conversations.value[index].messages;
};

const renameConversation = (index) => {
  ElMessageBox.prompt("请输入新的对话名称", "重命名对话", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    inputValue: conversations.value[index].title,
    inputValidator: (val) => !!val.trim(),
    inputErrorMessage: "名称不能为空",
  })
    .then(({ value }) => {
      conversations.value[index].title = value.trim();
      saveConversations();
      ElMessage.success("重命名成功");
    })
    .catch(() => {});
};

const deleteConversation = (index) => {
  ElMessageBox.confirm("确定删除该对话？", "提示", {
    confirmButtonText: "确定",
    cancelButtonText: "取消",
    type: "warning",
  })
    .then(() => {
      conversations.value.splice(index, 1);
      if (index === activeConversation.value) {
        currentMessages.value = conversations.value[0]?.messages || [];
        activeConversation.value = 0;
      }
      saveConversations();
      ElMessage.success("删除成功");
    })
    .catch(() => {});
};

// 选择热门主题
const selectTheme = (theme) => {
  storyInput.value = `请讲一个关于${theme}的童话故事`;
};

const sendStoryInput = async () => {
  if (!storyInput.value.trim()) {
    ElMessage.warning("请输入内容");
    return;
  }

  const content = storyInput.value.trim();

  const userMsg = {
    role: "user",
    content,
    timestamp: new Date().toLocaleTimeString(),
  };
  currentMessages.value.push(userMsg);
  saveConversations();
  scrollToBottom();
  storyInput.value = "";

  try {
    isSending.value = true;

    const aiMsg = {
      role: "ai",
      content: "",
      timestamp: new Date().toLocaleTimeString(),
    };
    currentMessages.value.push(aiMsg);
    saveConversations();

    const response = await fetch("http://localhost:5000/api/generate_story", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${authStore.token}`,
      },
      body: JSON.stringify({ prompt: content }),
    });

    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        isSending.value = false;
        break;
      }

      const chunk = decoder.decode(value);
      const lines = chunk.split("\n");
      for (const line of lines) {
        if (line.startsWith("data:")) {
          const data = JSON.parse(line.substring(5).trim());
          if (data.text) {
            aiMsg.content += data.text;
            currentMessages.value = [...currentMessages.value];
            saveConversations();
            scrollToBottom();
          }
        }
      }
    }
  } catch (error) {
    ElMessage.error("生成失败: " + error.message);
    isSending.value = false;
  }
};

const saveConversations = () => {
  conversations.value[activeConversation.value].messages =
    currentMessages.value;
  localStorage.setItem(
    `conversations_${authStore.user?.id}`,
    JSON.stringify(conversations.value)
  );
};

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
  transition: all 0.3s;
}

.conversation-list :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.2);
}

.conversation-list :deep(.el-menu-item.is-active) {
  background-color: rgba(255, 255, 255, 0.3);
}

.story-container {
  padding: 30px;
  background-color: white;
  height: 100vh;
  overflow-y: auto;
  background: linear-gradient(to bottom, #e6f7ff, #f0f9ff);
  background-image: url("https://img.freepik.com/free-vector/hand-painted-watercolor-pastel-sky-background_23-2148902771.jpg");
  background-size: cover;
  background-position: center;
  position: relative;
}

.story-container::before {
  content: "";
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 120px;
  background: url('data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 320"><path fill="%23ffffff" fill-opacity="0.6" d="M0,192L48,197.3C96,203,192,213,288,229.3C384,245,480,267,576,261.3C672,256,768,224,864,197.3C960,171,1056,149,1152,160C1248,171,1344,213,1392,234.7L1440,256L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z"></path></svg>');
  background-size: cover;
  background-position: bottom;
  z-index: 0;
}

.story-welcome {
  background: rgba(255, 255, 255, 0.85);
  padding: 25px;
  border-radius: 16px;
  margin-bottom: 25px;
  box-shadow: 0 5px 20px rgba(108, 92, 231, 0.1);
  border: 1px solid rgba(108, 92, 231, 0.15);
  position: relative;
  z-index: 1;
  text-align: center;
}

.story-welcome h2 {
  color: #7b2cbf;
  font-size: 28px;
  margin-bottom: 15px;
  background: linear-gradient(to right, #7b2cbf, #3c096c);
  -webkit-background-clip: text;
  background-clip: text; /* 添加这一行解决警告 */
  -webkit-text-fill-color: transparent;
}

.story-welcome p {
  color: #5a189a;
  margin-bottom: 20px;
  font-size: 16px;
}

.sentiment-btn {
  background: linear-gradient(to right, #ff9e7d, #ffd6a5);
  color: #5a189a;
  border: none;
  border-radius: 20px;
  padding: 10px 25px;
  font-weight: 600;
  box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
  transition: all 0.3s;
}

.sentiment-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 15px rgba(0, 0, 0, 0.15);
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 16px;
  margin-bottom: 20px;
  box-shadow: 0 5px 20px rgba(108, 92, 231, 0.08);
  position: relative;
  z-index: 1;
  min-height: 300px;
  border: 1px solid rgba(108, 92, 231, 0.1);
}

.message-item {
  margin-bottom: 25px;
}

.message-content {
  display: flex;
  max-width: 85%;
  margin: 0 auto;
}

.user .message-content {
  flex-direction: row-reverse;
}

.message-avatar {
  margin: 0 15px;
  display: flex;
  align-items: flex-start;
}

.message-avatar .el-avatar {
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.08);
  border: 2px solid white;
}

.message-text {
  flex: 1;
}

.message-meta {
  font-size: 13px;
  color: #7b2cbf;
  margin-bottom: 6px;
  display: flex;
  justify-content: space-between;
}

.message-role {
  font-weight: 600;
}

.message-time {
  opacity: 0.7;
}

.message-body {
  background: white;
  padding: 15px 20px;
  border-radius: 16px;
  box-shadow: 0 3px 10px rgba(0, 0, 0, 0.06);
  white-space: pre-line;
  line-height: 1.6;
  font-size: 15px;
  position: relative;
  border: 1px solid #f0f0f0;
}

.user .message-body {
  background: linear-gradient(to right, #9d4edd, #7b2cbf);
  color: white;
  border-radius: 16px 16px 4px 16px;
}

.ai .message-body {
  background: linear-gradient(to right, #e0c3fc, #c2e9fb);
  border-radius: 16px 16px 16px 4px;
}

/* 输入区域美化 */
.input-area {
  padding: 25px;
  background: rgba(255, 255, 255, 0.92);
  border-radius: 16px;
  box-shadow: 0 10px 30px rgba(108, 92, 231, 0.1);
  position: relative;
  z-index: 1;
  border: 1px solid rgba(108, 92, 231, 0.15);
}

.input-area::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, #ff9e7d, #9d4edd, #55efc4);
  border-radius: 2px;
  opacity: 0.7;
}

.popular-themes {
  margin-bottom: 20px;
}

.popular-themes h3 {
  color: #7b2cbf;
  margin-bottom: 15px;
  font-size: 17px;
  display: flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
}

.theme-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: center;
}

.theme-tag {
  background: linear-gradient(to right, #e0c3fc, #c2e9fb);
  color: #5a189a;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  transition: all 0.3s;
  padding: 8px 18px;
  font-weight: 500;
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.08);
}

.theme-tag:hover {
  transform: translateY(-3px);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.12);
  background: linear-gradient(to right, #d0b3fa, #b2d9f9);
}

.input-container {
  display: flex;
  gap: 15px;
  align-items: center;
}

.story-input {
  flex: 1;
}

.story-input :deep(.el-input__inner) {
  height: 52px;
  padding-left: 45px;
  border-radius: 16px;
  border: 2px solid #e0c3fc;
  font-size: 15px;
  transition: all 0.3s;
  background: rgba(255, 255, 255, 0.9);
}

.story-input :deep(.el-input__inner:focus) {
  border-color: #9d4edd;
  box-shadow: 0 0 0 2px rgba(157, 78, 221, 0.2);
}

.story-input :deep(.el-input__prefix) {
  left: 15px;
  color: #9d4edd;
  font-size: 20px;
}

.send-btn {
  background: linear-gradient(to right, #9d4edd, #7b2cbf);
  color: white;
  border: none;
  height: 52px;
  padding: 0 35px;
  border-radius: 16px;
  font-weight: 600;
  font-size: 16px;
  transition: all 0.3s;
  box-shadow: 0 5px 15px rgba(157, 78, 221, 0.3);
  display: flex;
  align-items: center;
  gap: 8px;
}

.send-btn:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(157, 78, 221, 0.4);
}

.send-btn:active {
  transform: translateY(1px);
}
</style>