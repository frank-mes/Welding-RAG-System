import streamlit as st
import google.generativeai as genai
from github import Github
import datetime
import time
import random
import os
from itertools import cycle

# ==========================================
# 1. SERVICE LAYER (智能引擎层)
# ==========================================
class WeldingService:
    def __init__(self, api_keys_str):
        self.api_enabled = False
        self.model_name = "None"
        self.working_keys = []
        
        # 解析密钥列表
        if api_keys_str:
            self.working_keys = [k.strip() for k in api_keys_str.split(",") if len(k.strip()) > 10]
        
        if self.working_keys:
            self.key_cycle = cycle(self.working_keys)
            self._reconfigure_engine()

    def _reconfigure_engine(self):
        """切换 API Key 并重新配置模型"""
        current_key = next(self.key_cycle)
        try:
            genai.configure(api_key=current_key)
            # 自动探测可用模型
            models = [m.name for m in genai.list_models() 
                     if 'generateContent' in m.supported_generation_methods]
            
            priority = ['models/gemini-2.0-flash', 'models/gemini-1.5-flash', 'models/gemini-pro']
            self.model_name = next((p for p in priority if p in models), models[0] if models else None)
            
            if self.model_name:
                self.model = genai.GenerativeModel(self.model_name)
                self.api_enabled = True
        except Exception as e:
            self.init_error = str(e)

    def get_solution(self, material, defect):
        if not self.api_enabled:
            return self.get_mock_response(material, defect)

        # 尝试次数为 Key 数量的 2 倍
        max_retries = len(self.working_keys) * 2
        wait_time = 15 # 初始冷却时间略微拉长，应对共享 IP 限制
        
        prompt = f"""你是一位资深国际焊接工程师(IWE)。
请针对材料【{material}】的【{defect}】缺陷进行深度分析。
要求：
1. 分析该材料的焊接性及缺陷成因（涉及微观组织）。
2. 给出具体的预热温度、层间温度和后热(PWHT)参数。
3. 列出推荐的焊材型号及保护气体配比。
请使用专业的 Markdown 格式输出，重要参数请加粗或使用表格。"""

        for i in range(max_retries):
            try:
                # 随机微延迟，错开并发峰值
                time.sleep(random.uniform(1.0, 3.0))
                
                response = self.model.generate_content(prompt)
                
                # 安全提取文本：处理 Gemini 的安全拦截抛出的 ValueError
                try:
                    return response.text
                except ValueError:
                    st.warning("⚠️ 检测到敏感内容拦截，已切换至基础方案。")
                    return self.get_mock_response(material, defect)
                
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg and i < max_retries - 1:
                    st.warning(f"🔄 节点繁忙，正在切换备用引擎并冷却 (尝试 {i+1}/{max_retries})...")
                    self._reconfigure_engine() # 核心：切换到下一个 Key
                    time.sleep(wait_time)
                    wait_time += 10 # 递增冷却
                    continue
                else:
                    st.error(f"❌ AI 引擎响应异常: {err_msg[:100]}")
                    break
        
        return self.get_mock_response(material, defect)

    def get_mock_response(self, material, defect):
        """本地兜底方案库"""
        return f"""### 🛡️ 专家建议 (本地库备份)
**注意**：当前 AI 引擎繁忙或受到云端限制，为您自动匹配基础修复方案。

**针对 {material} 的 {defect} 分析**：
1. **成因**：通常与热输入量控制不当、冷却速度过快或母材淬硬倾向有关。
2. **工艺建议**：
    - **预热**：建议温度控制在 150°C-250°C 之间。
    - **热输入**：采用小电流、多层多道焊，控制层间温度。
    - **消氢**：焊后立即执行 250°C x 2h 后热处理。
3. **检验**：建议进行 100% 超声波探伤 (UT) 或磁粉探伤 (MT)。"""

# ==========================================
# 2. DAO LAYER (数据持久化)
# ==========================================
class WeldingDAO:
    def __init__(self, token, repo_full_path):
        self.valid = False
        if token and "/" in repo_full_path:
            try:
                self.gh = Github(token)
                self.repo = self.gh.get_repo(repo_full_path)
                self.valid = True
            except:
                self.valid = False

    def save_record(self, material, solution):
        if not self.valid: return "⚠️ GitHub 存档未配置或权限不足"
        
        date_str = datetime.date.today().isoformat()
        path = f"solutions/{material}_{date_str}.md"
        content = f"# 焊接专家诊断报告\n\n- 材料: {material}\n- 生成日期: {datetime.datetime.now()}\n\n---\n\n{solution}"
        
        try:
            try:
                contents = self.repo.get_contents(path)
                self.repo.update_file(path, f"Update {material}", content, contents.sha, branch="main")
                return f"✅ 已更新云端档案: {path}"
            except:
                self.repo.create_file(path, f"Create {material}", content, branch="main")
                return f"✅ 已新建云端档案: {path}"
        except Exception as e:
            return f"❌ 同步失败: {str(e)[:50]}"

# ==========================================
# 3. UI LAYER (应用主逻辑)
# ==========================================

# 缓存资源，防止 Streamlit 频繁刷新导致 API 被封
@st.cache_resource
def init_welding_service(api_keys):
    return WeldingService(api_keys)

def main():
    st.set_page_config(page_title="焊接AI专家系统", page_icon="👨‍🏭", layout="centered")
    
    st.title("🛡️ 焊接缺陷 AI 诊断中心")
    st.caption("工业级 AI 辅助决策系统 | 基于 Hugging Face 容器部署")
    st.markdown("---")

    # 兼容性读取配置 (Hugging Face Secrets / Streamlit Secrets)
    gemini_keys = os.environ.get("GEMINI_KEY") or st.secrets.get("GEMINI_KEY", "")
    gh_token = os.environ.get("GH_TOKEN") or st.secrets.get("GH_TOKEN", "")
    repo_name = os.environ.get("REPO_NAME") or st.secrets.get("REPO_NAME", "frank-mes/Welding-RAG-System")

    # 初始化服务
    svc = init_welding_service(gemini_keys)

    # 侧边栏显示状态
    with st.sidebar:
        st.header("系统运行状态")
        if svc.api_enabled:
            st.success(f"在线：{svc.model_name}")
            st.info(f"备用引擎数: {len(svc.working_keys)}")
        else:
            st.error("离线：AI 引擎初始化失败")
            if hasattr(svc, 'init_error'):
                st.caption(f"错误信息: {svc.init_error}")
        st.divider()
        st.caption("建议配置多个 API Key 以应对频率限制。")

    # 输入区域
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            material = st.text_input("材料牌号", placeholder="如: Q345R / S32205")
        with col2:
            defect = st.text_input("缺陷类型", placeholder="如: 氢致裂纹 / 夹杂")

    if st.button("开始 AI 推理诊断", type="primary", use_container_width=True):
        if not material or not defect:
            st.warning("⚠️ 请输入完整的信息。")
            return

        with st.status("正在连接 AI 专家引擎并检索工艺规范...", expanded=True) as status:
            solution = svc.get_solution(material, defect)
            status.update(label="诊断报告生成完毕！", state="complete")
        
        # 显示结果
        st.markdown("---")
        st.subheader("💡 专家建议方案")
        st.markdown(solution)

        # 存档至 GitHub
        if gh_token:
            dao = WeldingDAO(gh_token, repo_name)
            with st.spinner("正在将报告同步至 GitHub 仓库..."):
                save_msg = dao.save_record(material, solution)
                st.toast(save_msg)

if __name__ == "__main__":
    main()
