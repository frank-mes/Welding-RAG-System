import streamlit as st
import google.generativeai as genai
from github import Github
import datetime
import time

# ==========================================
# 1. SERVICE LAYER (智能模型匹配版)
# ==========================================
class WeldingService:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        # 核心逻辑：自动寻找当前 Key 支持的、最合适的模型
        self.model_name = self._auto_detect_model()
        self.model = genai.GenerativeModel(self.model_name)

    def _auto_detect_model(self):
        """
        自动探测模型。解决 404 models/xxx not found 的终极方案。
        """
        try:
            # 获取所有支持生成内容（generateContent）的模型列表
            models = [m.name for m in genai.list_models() 
                      if 'generateContent' in m.supported_generation_methods]
            
            # 优先级排序：我们想要的模型
            # 1.5 Flash 最快最稳，1.5 Pro 最强，1.0 Pro 兼容性最高
            priority = ['models/gemini-1.5-flash', 'models/gemini-1.5-pro', 'models/gemini-pro']
            
            for p in priority:
                if p in models:
                    return p
            
            # 如果都不在，返回列表里的第一个
            return models[0] if models else 'gemini-pro'
        except Exception as e:
            st.error(f"无法获取模型列表: {e}")
            return 'gemini-pro' # 最后的兜底方案

    def get_solution(self, material, defect):
        max_retries = 3
        for i in range(max_retries):
            try:
                prompt = f"你是一位焊接专家。请针对材料【{material}】出现的【{defect}】缺陷，提供失效分析及修复建议。"
                response = self.model.generate_content(prompt)
                return response.text
            except Exception as e:
                if "429" in str(e) and i < max_retries - 1:
                    time.sleep(10)
                    continue
                raise e

# ==========================================
# 2. DAO LAYER & UI (保持简洁)
# ==========================================
def main():
    st.set_page_config(page_title="焊接AI专家", page_icon="👨‍🏭")
    st.title("🛡️ 焊接缺陷 AI 诊断中心")
    
    if "GEMINI_KEY" not in st.secrets:
        st.error("请在 Streamlit Secrets 中配置 GEMINI_KEY")
        return

    svc = WeldingService(st.secrets["GEMINI_KEY"])
    st.sidebar.info(f"🚀 已自动匹配模型: {svc.model_name}")

    with st.container(border=True):
        mat = st.text_input("材料牌号")
        dfc = st.text_input("缺陷类型")

    if st.button("生成专家方案", type="primary", use_container_width=True):
        try:
            with st.status("专家正在会诊...") as status:
                res = svc.get_solution(mat, dfc)
                status.update(label="方案生成成功！", state="complete")
            
            st.markdown("---")
            st.markdown(res)

            # GitHub 存档 (可选配置)
            if "GH_TOKEN" in st.secrets:
                dao = WeldingDAO(st.secrets["GH_TOKEN"], "welding-rag-system")
                path = dao.save_record(mat, res)
                st.toast(f"已同步至 GitHub: {path}")

        except Exception as e:
            st.error(f"运行出错: {e}")

# 以下是 DAO 类 (与之前一致，此处略)
class WeldingDAO:
    def __init__(self, token, repo_name):
        self.gh = Github(token)
        self.repo = self.gh.get_user().get_repo(repo_name)
    def save_record(self, material, solution):
        path = f"solutions/{material}_{datetime.date.today()}.md"
        content = f"# 焊接方案\n{solution}"
        try:
            self.repo.create_file(path, f"Upload {material}", content, branch="main")
            return path
        except: return "已存在备份"

if __name__ == "__main__":
    main()
