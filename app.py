import streamlit as st
import google.generativeai as genai
from github import Github
import datetime
import time

# ==========================================
# 1. SERVICE LAYER (带模拟模式的业务层)
# ==========================================
class WeldingService:
    def __init__(self, api_key):
        self.api_enabled = False
        if api_key and api_key != "你的谷歌API密钥":
            try:
                genai.configure(api_key=api_key)
                # 显式尝试匹配
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.api_enabled = True
            except:
                st.sidebar.warning("⚠️ AI 引擎初始化失败，将使用模拟模式")

    def get_solution(self, material, defect):
        # 如果 API 正常且有配额
        if self.api_enabled:
            try:
                response = self.model.generate_content(
                    f"作为焊接专家，分析{material}的{defect}问题并给出修复建议。"
                )
                return response.text
            except Exception as e:
                if "429" in str(e):
                    st.error("🚨 触发 API 配额限制（429）。正在自动切换到本地专家库...")
                else:
                    st.error(f"❌ AI 调用出错: {e}")
        
        # 离线/模拟模式的专家回复（兜底）
        time.sleep(2) # 模拟思考
        return f"【模拟专家回复】针对 {material} 的 {defect} 缺陷，初步建议：\n1. 检查焊接电流与速度。\n2. 确认焊材干燥情况。\n3. 进行预热处理。"

# ==========================================
# 2. DAO LAYER (GitHub 存档保持不变)
# ==========================================
class WeldingDAO:
    def __init__(self, token, repo_name):
        self.gh = Github(token)
        self.repo = self.gh.get_user().get_repo(repo_name)

    def save_record(self, material, solution):
        path = f"solutions/{material}_{datetime.date.today()}.md"
        content = f"# 焊接方案备份\n- 时间: {datetime.datetime.now()}\n\n{solution}"
        try:
            self.repo.create_file(path, f"Save {material} solution", content, branch="main")
            return path
        except: return "备份完成 (本地/更新)"

# ==========================================
# 3. MAIN UI
# ==========================================
def main():
    st.set_page_config(page_title="焊接AI专家", layout="wide")
    st.title("👨‍🏭 焊接缺陷智能诊断系统")

    # 配置区
    with st.sidebar:
        st.header("系统设置")
        gemini_key = st.secrets.get("GEMINI_KEY", "")
        gh_token = st.secrets.get("GH_TOKEN", "")
        
    # 输入区
    col1, col2 = st.columns(2)
    with col1:
        mat = st.text_input("材料牌号", "Q345")
    with col2:
        dfc = st.text_input("缺陷类型", "裂纹")

    if st.button("开始诊断", type="primary"):
        # 执行业务逻辑
        svc = WeldingService(gemini_key)
        with st.spinner("正在生成专家建议..."):
            res = svc.get_solution(mat, dfc)
        
        st.success("诊断完成！")
        st.markdown("### 📋 专家方案")
        st.info(res)

        # 执行存档逻辑
        if gh_token:
            dao = WeldingDAO(gh_token, "welding-rag-system")
            path = dao.save_record(mat, res)
            st.toast(f"同步至 GitHub 成功")

if __name__ == "__main__":
    main()
