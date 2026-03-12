import streamlit as st
import google.generativeai as genai
from github import Github
import datetime

# ==========================================
# 1. SERVICE LAYER (业务逻辑层 - 处理AI推理)
# ==========================================
class WeldingService:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')

    def get_solution(self, material, defect):
        prompt = f"你是一位焊接专家。请针对材料【{material}】出现的【{defect}】缺陷，提供失效分析及修复建议。"
        response = self.model.generate_content(prompt)
        return response.text

# ==========================================
# 2. DAO LAYER (数据访问层 - 处理GitHub存储)
# ==========================================
class WeldingDAO:
    def __init__(self, token, repo_name):
        self.gh = Github(token)
        self.repo = self.gh.get_user().get_repo(repo_name)

    def save_record(self, material, solution):
        path = f"solutions/{material}_{datetime.date.today()}.md"
        content = f"# 焊接方案备份\n生成时间: {datetime.datetime.now()}\n\n{solution}"
        self.repo.create_file(path, f"Upload solution for {material}", content, branch="main")
        return path

# ==========================================
# 3. CONTROLLER & VIEW (表现层 - 界面与调度)
# ==========================================
def main():
    st.set_page_config(page_title="焊接AI专家", layout="centered")
    st.title("👨‍🏭 焊接缺陷 AI 诊断系统")
    st.info("基于 Gemini 大模型 | 自动同步至 GitHub")

    # 输入区域
    col1, col2 = st.columns(2)
    with col1:
        material = st.text_input("材料牌号", "Q345B")
    with col2:
        defect = st.text_input("焊接缺陷", "气孔")

    # 核心按钮逻辑
    if st.button("开始推理并备份", type="primary"):
        if not material or not defect:
            st.warning("请输入完整信息")
            return

        try:
            # A. 调用 Service 推理
            service = WeldingService(st.secrets["GEMINI_KEY"])
            with st.spinner("AI 专家正在思考..."):
                solution = service.get_solution(material, defect)
            
            st.subheader("💡 专家解决方案")
            st.markdown(solution)

            # B. 调用 DAO 存储到 GitHub
            dao = WeldingDAO(st.secrets["GH_TOKEN"], "welding-rag-system")
            file_path = dao.save_record(material, solution)
            st.success(f"✅ 方案已同步至仓库路径: {file_path}")

        except Exception as e:
            st.error(f"发生错误: {str(e)}")
            st.info("提示：请检查 Streamlit Secrets 是否配置了正确的 API Key")

if __name__ == "__main__":
    main()
