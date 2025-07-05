<template>
  <div class="home-container">
    <el-container>
      <!-- 侧边栏 -->
      <el-aside width="250px" class="sidebar">
        <div class="user-info">
          <el-avatar :size="50" :src="userAvatar" />
          <span class="username">{{ authStore.user?.username }}</span>
          <el-button type="text" @click="authStore.logout" class="logout-btn">退出登录</el-button>
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
            <div style="display: flex; justify-content: space-between; align-items: center; width: 100%;">
              <span>{{ conv.title }}</span>
              <div style="display: flex; gap: 5px;">
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
          <h2>儿童故事乐园</h2>
          <p><strong>你好！我是故事精灵，可以为你讲故事并分析情感~</strong></p>
        </div>

        <div class="message-list" ref="messageList" v-show="currentMessages.length > 0">
          <div
            v-for="(msg, index) in currentMessages"
            :key="index"
            :class="['message-item', msg.role]"
          >
            <div class="message-content">
              <div class="message-avatar">
                <el-avatar :size="40" :src="msg.role === 'user' ? userAvatar : botAvatar" />
              </div>
              <div class="message-text">
                <div class="message-meta">
                  <span class="message-role">{{ msg.role === 'user' ? '你' : 'AI助手' }}</span>
                  <span class="message-time">{{ msg.timestamp }}</span>
                  <el-button
                    v-if="msg.role === 'ai' && msg.content.length > 10"
                    size="small"
                    @click="analyzeSentiment(msg.content)"
                    class="sentiment-btn"
                  >
                    情感分析
                  </el-button>
                </div>
                <div class="message-body">{{ msg.content }}</div>
                <div v-if="msg.sentiment" class="sentiment-result">
                  <el-tag :type="getSentimentTagType(msg.sentiment.label)">
                    {{ getSentimentLabel(msg.sentiment.label) }}
                    ({{ (msg.sentiment.score * 100).toFixed(1) }}%)
                  </el-tag>
                  <p v-if="msg.sentiment.recommendation" class="recommendation">{{ msg.sentiment.recommendation }}</p>
                  <p v-if="msg.sentiment.detail" class="detail">{{ msg.sentiment.detail }}</p>
                  <el-collapse>
                    <el-collapse-item title="查看详细分析">
                      <div
                        v-for="(item, idx) in msg.sentiment.analysis"
                        :key="idx"
                        class="analysis-item"
                      >
                        <el-tag :type="getSentimentTagType(item.label)" size="small">
                          {{ getSentimentLabel(item.label) }}
                        </el-tag>
                        <span class="analysis-score">{{ (item.score * 100).toFixed(1) }}%</span>
                      </div>
                    </el-collapse-item>
                  </el-collapse>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 输入区域 -->
        <div class="input-area">
          <el-input
            v-model="storyInput"
            placeholder="请输入你想听的故事内容..."
            @keyup.enter="sendStoryInput"
            clearable
          />
          <el-button
            type="primary"
            @click="sendStoryInput"
            :loading="isSending"
            class="send-btn"
          >
            发送
          </el-button>
        </div>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from "vue";
import { useAuthStore } from "../stores/auth";
import axios from "axios";
import { ElMessage, ElMessageBox } from "element-plus";
import { Plus, Delete, Edit } from "@element-plus/icons-vue";

const authStore = useAuthStore();

const storyInput = ref("");
const isSending = ref(false);
const isAnalyzing = ref(false);

const conversations = ref([]);
const currentMessages = ref([]);
const activeConversation = ref(0);
const messageList = ref(null);

const userAvatar = computed(() =>
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

const analyzeSentiment = async (text) => {
  try {
    isAnalyzing.value = true;
    const res = await axios.post(
      "http://localhost:5000/api/analyze_sentiment",
      { text },
      { headers: { Authorization: `Bearer ${authStore.token}` } }
    );
    const data = res.data;

    const msgIndex = currentMessages.value.findIndex((msg) => msg.content === text);
    if (msgIndex !== -1) {
      currentMessages.value[msgIndex].sentiment = {
        label: data.primary_sentiment,
        score: data.primary_score,
        analysis: data.analysis,
        recommendation: data.recommendation,
        detail: data.detail,
      };
      saveConversations();
    }
  } catch (e) {
    ElMessage.error("分析失败: " + e.message);
  } finally {
    isAnalyzing.value = false;
  }
};

const getSentimentLabel = (label) =>
  ({ LABEL_0: "负面", LABEL_1: "中性", LABEL_2: "正面" }[label] || label);
const getSentimentTagType = (label) =>
  ({ LABEL_0: "danger", LABEL_1: "info", LABEL_2: "success" }[label] || "");

const saveConversations = () => {
  conversations.value[activeConversation.value].messages = currentMessages.value;
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
}

.conversation-list :deep(.el-menu-item.is-active) {
  background-color: rgba(255, 255, 255, 0.3);
}

.story-container {
  padding: 30px;
  background-color: white;
  height: 100vh;
  overflow-y: auto;
  background-image: url("https://img.freepik.com/free-vector/hand-painted-watercolor-pastel-sky-background_23-2148902771.jpg");
  background-size: cover;
  background-position: center;
}

.story-welcome {
  background-color: rgba(255, 255, 255, 0.85);
  padding: 30px;
  border-radius: 15px;
  margin-bottom: 30px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
}

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
  white-space: pre-line;
}

.sentiment-result {
  margin-top: 10px;
  padding: 10px;
  background-color: rgba(255, 255, 255, 0.8);
  border-radius: 8px;
}

.recommendation {
  margin: 5px 0 0;
  font-size: 0.9em;
  color: #666;
}

.detail {
  margin: 5px 0 0;
  font-size: 0.9em;
  color: #444;
  white-space: pre-line;
}

.analysis-item {
  display: flex;
  align-items: center;
  margin: 5px 0;
  padding: 5px;
  background-color: rgba(255, 255, 255, 0.5);
  border-radius: 4px;
}

.analysis-score {
  font-size: 0.9em;
  color: #666;
}

.input-area {
  padding: 20px;
  background-color: rgba(255, 255, 255, 0.9);
  border-radius: 15px;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
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

.user .message-body {
  background: linear-gradient(135deg, #6c5ce7 0%, #a29bfe 100%);
  color: white;
}

.sentiment-btn {
  margin-left: 10px;
  background: linear-gradient(135deg, #ff7675 0%, #fdcb6e 100%);
  color: white;
  border: none;
}

.send-btn {
  margin-top: 10px;
  background: linear-gradient(135deg, #00b894 0%, #55efc4 100%);
  color: white;
  border: none;
}
</style>
