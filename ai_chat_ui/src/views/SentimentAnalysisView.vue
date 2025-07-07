<template>
  <div class="sentiment-dashboard">
    <!-- 顶部导航栏 -->
    <el-header class="dashboard-header">
      <div class="header-left">
        <el-button type="text" @click="goBack" class="back-btn">
          <el-icon><ArrowLeft /></el-icon>返回主页
        </el-button>
      </div>
      <div class="header-center">
        <h1>情感分析中心</h1>
      </div>
      <div class="header-right">
        <el-avatar :size="40" :src="userAvatar" />
        <span class="username">{{ authStore.user?.username }}</span>
      </div>
    </el-header>

    <el-main class="dashboard-content">
      <!-- 概览卡片 -->
      <el-row :gutter="20" class="overview-cards">
        <el-col :span="8">
          <el-card shadow="hover" class="sentiment-card">
            <template #header>
              <div class="card-header">
                <el-icon><PieChart /></el-icon>
                <span>情感分布</span>
              </div>
            </template>
            <div v-if="overallSentiment" class="sentiment-chart">
              <el-progress
                type="dashboard"
                :percentage="Math.min(overallSentiment.score * 100, 100)"
                :status="getSentimentStatus(overallSentiment.label)"
                :format="formatSentiment"
              />
              <div class="sentiment-stats">
                <div
                  v-for="(day, index) in dailyAnalysis.slice(0, 3)"
                  :key="index"
                  class="stat-item"
                >
                  <span class="stat-date">{{ formatTimestamp(day.date) }}</span>
                  <el-tag :type="getSentimentTagType(day.label)" effect="dark">
                    {{ getSentimentLabel(day.label) }}
                  </el-tag>
                </div>
              </div>
            </div>
            <el-skeleton :rows="3" animated v-else />
          </el-card>
        </el-col>

        <el-col :span="8">
          <el-card shadow="hover" class="recommendation-card">
            <template #header>
              <div class="card-header">
                <el-icon><Lightbulb /></el-icon>
                <span>专业建议</span>
              </div>
            </template>
            <div v-if="overallSentiment" class="recommendation-content">
              <h3
                :class="
                  'recommendation-title ' +
                  getSentimentStatus(overallSentiment.label)
                "
              >
                {{ overallSentiment.recommendation }}
              </h3>
              <el-divider />
              <div class="action-list">
                <el-tag
                  v-for="(action, idx) in getRecommendationActions(
                    overallSentiment.label
                  )"
                  :key="idx"
                  :type="getSentimentTagType(overallSentiment.label)"
                  effect="light"
                  class="action-tag"
                >
                  <el-icon><Check /></el-icon>
                  {{ action }}
                </el-tag>
              </div>
            </div>
            <el-skeleton :rows="3" animated v-else />
          </el-card>
        </el-col>

        <el-col :span="8">
          <el-card shadow="hover" class="resources-card">
            <template #header>
              <div class="card-header">
                <el-icon><Connection /></el-icon>
                <span>支持资源</span>
              </div>
            </template>
            <div class="resource-list">
              <div
                v-for="(resource, idx) in resources"
                :key="idx"
                class="resource-item"
              >
                <el-icon><Link /></el-icon>
                <a :href="resource.link" target="_blank">{{ resource.name }}</a>
              </div>
            </div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 趋势图表 -->
      <el-card shadow="hover" class="trend-card">
        <template #header>
          <div class="card-header">
            <el-icon><TrendCharts /></el-icon>
            <span>情感趋势</span>
          </div>
        </template>
        <div v-if="dailyAnalysis.length > 0" class="trend-container">
          <div class="chart-wrapper">
            <div
              v-for="(day, index) in dailyAnalysis"
              :key="index"
              class="trend-bar"
              :style="{
                height: `${Math.min(day.score * 100, 100)}%`,
                backgroundColor: getSentimentColor(day.label),
              }"
              :title="`${formatTimestamp(day.date)}: ${getSentimentLabel(
                day.label
              )} (${Math.min(day.score * 100, 100).toFixed(1)}%)`"
            >
              <div class="bar-value">
                {{ Math.min(day.score * 100, 100).toFixed(0) }}%
              </div>
            </div>
          </div>
          <div class="chart-labels">
            <div
              v-for="(day, index) in dailyAnalysis"
              :key="index"
              class="chart-label"
            >
              {{ formatTimestamp(day.date) }}
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无趋势数据" />
      </el-card>

      <!-- 消息样本 -->
      <el-card shadow="hover" class="samples-card">
        <template #header>
          <div class="card-header">
            <el-icon><ChatLineRound /></el-icon>
            <span>代表性消息</span>
          </div>
        </template>
        <div v-if="sampleMessages.length > 0" class="samples-container">
          <div class="message-grid">
            <div
              v-for="(msg, index) in sampleMessages"
              :key="index"
              :class="
                'message-card ' + getSentimentTagType(msg.sentiment.label)
              "
            >
              <div class="message-header">
                <span class="message-time">{{
                  formatTimestamp(msg.timestamp)
                }}</span>
                <el-tag
                  :type="getSentimentTagType(msg.sentiment.label)"
                  effect="dark"
                  class="sentiment-tag"
                >
                  {{ getSentimentLabel(msg.sentiment.label) }} ({{
                    Math.min(msg.sentiment.score * 100, 100).toFixed(1)
                  }}%)
                </el-tag>
              </div>
              <div class="message-content">{{ msg.content }}</div>
            </div>
          </div>
        </div>
        <el-empty v-else description="暂无消息样本" />
      </el-card>
    </el-main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import {
  ArrowLeft,
  PieChart,
  Lightbulb,
  Connection,
  Link,
  Check,
  TrendCharts,
  ChatLineRound,
} from "@element-plus/icons-vue";
import axios from "axios";
import { ElMessage } from "element-plus";

const router = useRouter();
const authStore = useAuthStore();

const userAvatar = computed(
  () =>
    `https://api.dicebear.com/7.x/initials/svg?seed=${authStore.user?.username}&background=6c5ce7&color=fff`
);

const overallSentiment = ref(null);
const dailyAnalysis = ref([]);
const sampleMessages = ref([]);
const messages = ref([]);
const loading = ref(true);
const error = ref("");

const resources = ref([
  { name: "心理健康热线: 12320", link: "tel:12320" },
  { name: "北京心理援助热线", link: "tel:01082951332" },
  { name: "全国24小时心理援助", link: "tel:8008101117" },
  { name: "心理咨询指南", link: "https://www.xinli001.com" },
]);

const getRecentMessages = async () => {
  try {
    loading.value = true;
    error.value = "";

    const saved = localStorage.getItem(`conversations_${authStore.user?.id}`);
    if (saved) {
      const conversations = JSON.parse(saved);
      messages.value = conversations.flatMap((conv) => conv.messages);
      return messages.value;
    }
    return [];
  } catch (err) {
    console.error("获取消息失败:", err);
    ElMessage.error("获取聊天记录失败");
    return [];
  }
};

const analyzeMessages = async (messages) => {
  try {
    if (messages.length === 0) return null;

    const res = await axios.post(
      "http://localhost:5000/api/analyze_sentiment2",
      { messages },
      { headers: { Authorization: `Bearer ${authStore.token}` } }
    );

    console.log("情感分析结果:", res.data);
    return res.data;
  } catch (err) {
    console.error("情感分析失败:", err);
    ElMessage.error("情感分析失败: " + err.message);
    return null;
  } finally {
    loading.value = false;
  }
};

const formatSentiment = (percentage) => {
  return `${Math.min(percentage, 100).toFixed(1)}% ${getSentimentLabel(
    overallSentiment.value.label
  )}`;
};

const getSentimentLabel = (label) => {
  // 处理可能的错误标签
  if (label.includes("负面") || label === "LABEL_0") return "负面";
  if (label.includes("中性") || label === "LABEL_1") return "中性";
  if (label.includes("正面") || label === "LABEL_2") return "正面";

  // 处理特殊错误标签
  const mapping = {
    中佳: "中性",
    众团: "中性",
    负面: "负面",
    正面: "正面",
  };

  return mapping[label] || label;
};

const getSentimentTagType = (label) =>
  ({ 负面: "danger", 中性: "info", 正面: "success" }[
    getSentimentLabel(label)
  ] || "");

const getSentimentStatus = (label) =>
  ({ 负面: "exception", 中性: "", 正面: "success" }[getSentimentLabel(label)] ||
  "");

const getSentimentColor = (label) =>
  ({ 负面: "#ff4d4f", 中性: "#faad14", 正面: "#52c41a" }[
    getSentimentLabel(label)
  ] || "#999");

const getRecommendationActions = (label) => {
  const sentiment = getSentimentLabel(label);
  const actions = {
    负面: ["与朋友倾诉", "进行深呼吸练习", "听舒缓音乐", "联系心理咨询师"],
    中性: ["尝试新活动", "记录每日心情", "与家人交流"],
    正面: ["分享积极体验", "帮助他人", "继续保持良好状态"],
  };
  return actions[sentiment] || [];
};

const formatTimestamp = (timestamp) => {
  if (!timestamp) return "未知时间";

  try {
    // 处理可能的无效时间格式
    if (typeof timestamp === "string" && timestamp.includes("T")) {
      const date = new Date(timestamp);
      if (isNaN(date.getTime())) return "未知时间";
      return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${date
        .getMinutes()
        .toString()
        .padStart(2, "0")}`;
    }

    // 处理日期字符串 (YYYY-MM-DD)
    if (
      typeof timestamp === "string" &&
      timestamp.match(/^\d{4}-\d{2}-\d{2}$/)
    ) {
      return timestamp.split("-").slice(1).join("/");
    }

    return "未知时间";
  } catch {
    return "未知时间";
  }
};

const goBack = () => {
  router.push("/");
};

onMounted(async () => {
  const messages = await getRecentMessages();
  if (messages.length > 0) {
    const analysis = await analyzeMessages(messages);
    if (analysis) {
      // 确保分数在合理范围内
      if (analysis.overall && analysis.overall.score > 1) {
        analysis.overall.score = analysis.overall.score / 100;
      }

      // 修正日期格式
      analysis.daily.forEach((day) => {
        if (day.score > 1) day.score = day.score / 100;

        // 确保日期格式正确
        if (day.date && day.date.includes("T")) {
          day.date = day.date.split("T")[0];
        }
      });

      // 修正样本消息格式
      analysis.samples.forEach((sample) => {
        if (sample.sentiment.score > 1) {
          sample.sentiment.score = sample.sentiment.score / 100;
        }

        // 确保时间戳格式正确
        if (sample.timestamp && sample.timestamp.includes("T")) {
          // 保持原格式
        }
      });

      overallSentiment.value = analysis.overall;
      dailyAnalysis.value = analysis.daily;
      sampleMessages.value = analysis.samples;
    }
  } else {
    loading.value = false;
  }
});
</script>


<style scoped>
.sentiment-dashboard {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background-color: #f5f7fa;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 30px;
  background: linear-gradient(135deg, #6c5ce7 0%, #a29bfe 100%);
  color: white;
  box-shadow: 0 2px 10px rgba(108, 92, 231, 0.3);
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 15px;
}

.header-center h1 {
  margin: 0;
  font-weight: 500;
  font-size: 1.5rem;
}

.back-btn {
  color: white;
  font-weight: 500;
}

.username {
  font-weight: 500;
}

.dashboard-content {
  padding: 20px;
  flex: 1;
  overflow-y: auto;
}

.overview-cards {
  margin-bottom: 20px;
}

.el-card {
  border-radius: 12px;
  border: none;
  transition: transform 0.3s;
}

.el-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 500;
}

.sentiment-chart {
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding: 10px 0;
}

.sentiment-stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-date {
  font-size: 0.9rem;
  color: #666;
}

.recommendation-content {
  padding: 10px;
}

.recommendation-title {
  font-size: 1.1rem;
  padding: 12px 15px;
  border-radius: 8px;
  margin-bottom: 15px;
  line-height: 1.5;
}

.recommendation-title.success {
  background-color: #f6ffed;
  color: #52c41a;
  border-left: 4px solid #52c41a;
}

.recommendation-title.exception {
  background-color: #fff2f0;
  color: #ff4d4f;
  border-left: 4px solid #ff4d4f;
}

.recommendation-title.info {
  background-color: #e6f7ff;
  color: #1890ff;
  border-left: 4px solid #1890ff;
}

.action-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.action-tag {
  cursor: pointer;
  transition: all 0.3s;
  padding: 8px 15px;
  border-radius: 20px;
}

.action-tag:hover {
  opacity: 0.8;
  transform: scale(1.05);
}

.resource-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.resource-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  transition: all 0.3s;
  background-color: #f8f9fa;
}

.resource-item:hover {
  background-color: #e6f7ff;
  transform: translateX(5px);
}

.resource-item a {
  color: #1890ff;
  text-decoration: none;
  font-weight: 500;
}

.resource-item a:hover {
  text-decoration: underline;
}

.trend-card {
  margin-bottom: 20px;
}

.trend-container {
  display: flex;
  flex-direction: column;
  height: 300px;
}

.chart-wrapper {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  flex: 1;
  gap: 15px;
  padding: 0 20px;
  background-color: #f8f9fa;
  border-radius: 8px;
  margin: 0 15px;
}

.trend-bar {
  flex: 1;
  max-width: 70px;
  border-radius: 8px 8px 0 0;
  transition: height 0.5s ease;
  cursor: pointer;
  position: relative;
  display: flex;
  justify-content: center;
}

.trend-bar:hover {
  opacity: 0.9;
  transform: scale(1.05);
}

.bar-value {
  position: absolute;
  top: -25px;
  font-size: 12px;
  font-weight: bold;
  color: #333;
}

.chart-labels {
  display: flex;
  justify-content: space-around;
  padding: 10px 20px;
  border-top: 1px solid #eee;
}

.chart-label {
  font-size: 0.8rem;
  color: #666;
  text-align: center;
  width: 60px;
}

.samples-container {
  padding: 10px;
}

.message-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.message-card {
  border-radius: 10px;
  padding: 15px;
  transition: all 0.3s;
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.08);
}

.message-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}

.message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.message-time {
  font-size: 0.85rem;
  color: #666;
}

.message-content {
  line-height: 1.6;
  padding: 5px 0;
}

/* 情感卡片颜色 */
.message-card.success {
  background: linear-gradient(to right, #f6ffed, #e6ffdb);
  border-left: 4px solid #52c41a;
}

.message-card.danger {
  background: linear-gradient(to right, #fff2f0, #ffccc7);
  border-left: 4px solid #ff4d4f;
}

.message-card.info {
  background: linear-gradient(to right, #e6f7ff, #bae7ff);
  border-left: 4px solid #1890ff;
}

@media (max-width: 992px) {
  .overview-cards .el-col {
    margin-bottom: 20px;
  }

  .chart-wrapper {
    padding: 0 10px;
  }

  .trend-bar {
    max-width: 50px;
  }
}

@media (max-width: 768px) {
  .dashboard-header {
    flex-direction: column;
    padding: 15px;
    gap: 10px;
  }

  .header-center h1 {
    font-size: 1.2rem;
  }

  .overview-cards .el-col {
    width: 100%;
  }

  .sentiment-chart {
    flex-direction: column;
  }

  .message-grid {
    grid-template-columns: 1fr;
  }
}
</style>