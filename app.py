import streamlit as st
import google.generativeai as genai
from github import Github
import datetime
import time  # 导入时间库用于处理重试等待

# ==========================================
# 1. SERVICE LAYER (修复了 429 Bug 的版本)
# ==========================================
class WeldingService:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model_name = self._get_best_model()
        self.model = genai.GenerativeModel(self.model_name)

    def _get_best_model(self):
        try:
            available_models = [m.name for m in genai.list_models() 
                               if 'generateContent' in m.supported_generation_methods]
            for preferred in ['models/gemini-1.5-flash', 'models/gemini-pro']:
                if preferred in available_models:
                    return preferred
            return available_models[0] if available_models else 'gemini-pro'
        except:
            return 'gemini-pro'

    def get_solution(self, material, defect):
        # --- 核心修复：自动重试逻辑 ---
        max_retries = 3  # 最大重试次数
        retry_delay = 5  # 初始等待秒数
        
        for i in range(max_retries):
            try:
                prompt = f"你是一位焊接专家。请针对材料【{material}】出现的【{defect}】缺陷，提供失效分析及修复建议。"
                response = self.model.generate_content(prompt)
                return response.text
            except Exception as e:
                # 如果是频率限制错误 (429)
                if "429" in str(e) and i < max_retries - 1:
                    st.warning(f"⚠️ API 繁忙 (429)，正在进行第 {i+1} 次重试，请稍候...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 每次等待时间翻倍
                    continue
                else:
                    # 其他错误或超过重试次数，则抛出异常
                    raise e

# ==========================================
# 2. DAO LAYER (保持不变)
# ==========================================
class WeldingDAO:
    def __init__(self, token, repo_name):
        self.gh = Github(token)
        self.repo = self.gh.get_user().get_repo(repo_name)

    def save_record(self, material, solution):
        path = f"solutions/{material}_{datetime.date.today()}.md"
        content = f"# 焊接方案备份\n- 材料: {material}\n- 时间: {datetime.datetime.now()}\n\n{solution}"
        try:
            self.repo.create_file(path, f"Welding solution for {material}", content, branch="main")
            return path
        except Exception as e:
            if "already exists" in str(e):
                return "文件已存在（无需重复上传）"
            raise e

# ==========================================
# 3. CONTROLLER & VIEW (保持不变)
# ==========================================
def main():
    st.set_page_config(page_title="焊接AI专家系统", page_icon="👨‍🏭")
    st.title("🛡️ 焊接缺陷 AI 诊断中心")
    st.caption("基于 Gemini 大模型架构 | 已集成抗压重试机制")

    with st.sidebar:
        st.header("系统状态")
        if "GEMINI_KEY" in st.secrets:
            st.success("API Key 已配置")
        else:
            st.error("API Key 缺失")

    with st.container(border=True):
        material = st.text_input("材料牌号", placeholder="例如: 316L 不锈钢")
        defect = st.text_input("焊接缺陷类型", placeholder="例如: 气孔")

    if st.button("开始 AI 推理", type="primary", use_container_width=True):
        if not material or not defect:
            st.warning("⚠️ 请输入完整的信息。")
            return

        try:
            service = WeldingService(st.secrets["GEMINI_KEY"])
            
            with st.status("正在联系专家模型并生成方案...", expanded=True) as status:
                st.write(f"正在使用模型: `{service.model_name}`")
                solution = service.get_solution(material, defect)
                status.update(label="推理完成！", state="complete")
            
            st.divider()
            st.subheader("💡 专家建议方案")
            st.markdown(solution)

            if "GH_TOKEN" in st.secrets:
                dao = WeldingDAO(st.secrets["GH_TOKEN"], "welding-rag-system")
                file_path = dao.save_record(material, solution)
                st.toast(f"同步成功: {file_path}", icon="✅")
            
        except Exception as e:
            if "429" in str(e):
                st.error("❌ 频率限制：谷歌 API 免费配额暂时用尽，请等待 1 分钟后再试。")
            else:
                st.error(f"❌ 系统故障: {str(e)}")

if __name__ == "__main__":
    main()
