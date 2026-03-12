import streamlit as st
import google.generativeai as genai
from github import Github
import datetime

# ==========================================
# 1. SERVICE LAYER (业务逻辑层)
# ==========================================
class WeldingService:
    def __init__(self, api_key):
        genai.configure(api_key=api_key)
        # 自动尝试获取当前可用的最新模型
        self.model_name = self._get_best_model()
        self.model = genai.GenerativeModel(self.model_name)

    def _get_best_model(self):
        """自动检测账户下可用的最佳模型"""
        try:
            available_models = [m.name for m in genai.list_models() 
                               if 'generateContent' in m.supported_generation_methods]
            # 优先级排序：gemini-pro 是最稳妥的兼容项
            for preferred in ['models/gemini-1.5-flash', 'models/gemini-pro']:
                if preferred in available_models:
                    return preferred
            return available_models[0] if available_models else 'gemini-pro'
        except:
            return 'gemini-pro' # 兜底策略

    def get_solution(self, material, defect):
        prompt = f"你是一位焊接专家。请针对材料【{material}】出现的【{defect}】缺陷，提供失效分析及详细的修复建议。"
        response = self.model.generate_content(prompt)
        return response.text

# ==========================================
# 2. DAO LAYER (数据访问层)
# ==========================================
class WeldingDAO:
    def __init__(self, token, repo_name):
        self.gh = Github(token)
        # 获取当前授权用户下的仓库
        self.repo = self.gh.get_user().get_repo(repo_name)

    def save_record(self, material, solution):
        # 确保目录存在
        path = f"solutions/{material}_{datetime.date.today()}.md"
        content = f"# 焊接方案备份\n- 材料: {material}\n- 时间: {datetime.datetime.now()}\n\n{solution}"
        
        try:
            # 尝试创建文件
            self.repo.create_file(path, f"Welding solution for {material}", content, branch="main")
            return path
        except Exception as e:
            # 如果文件已存在则更新，或捕获权限问题
            if "already exists" in str(e):
                return "文件已存在（无需重复上传）"
            raise e

# ==========================================
# 3. CONTROLLER & VIEW (界面与逻辑调度)
# ==========================================
def main():
    st.set_page_config(page_title="焊接AI专家系统", page_icon="👨‍🏭")
    
    st.title("🛡️ 焊接缺陷 AI 诊断中心")
    st.caption("基于 Gemini 大模型架构 | 大厂 MVC 模式开发")

    # 侧边栏展示系统状态
    with st.sidebar:
        st.header("系统状态")
        if "GEMINI_KEY" in st.secrets:
            st.success("API Key 已配置")
        else:
            st.error("API Key 缺失")

    # 输入区域
    with st.container(border=True):
        material = st.text_input("材料牌号", placeholder="例如: 316L 不锈钢")
        defect = st.text_input("焊接缺陷类型", placeholder="例如: 晶间腐蚀 或 气孔")

    if st.button("开始 AI 推理", type="primary", use_container_width=True):
        if not material or not defect:
            st.warning("⚠️ 请输入完整的信息。")
            return

        try:
            # A. 初始化服务
            service = WeldingService(st.secrets["GEMINI_KEY"])
            
            # B. 执行推理
            with st.status("正在联系专家模型并生成方案...", expanded=True) as status:
                st.write(f"正在使用模型: `{service.model_name}`")
                solution = service.get_solution(material, defect)
                status.update(label="推理完成！", state="complete")
            
            # C. 展示结果
            st.divider()
            st.subheader("💡 专家建议方案")
            st.markdown(solution)

            # D. 同步至 GitHub
            if "GH_TOKEN" in st.secrets:
                dao = WeldingDAO(st.secrets["GH_TOKEN"], "welding-rag-system")
                file_path = dao.save_record(material, solution)
                st.toast(f"同步成功: {file_path}", icon="✅")
            
        except Exception as e:
            st.error(f"❌ 系统故障: {str(e)}")
            st.info("排错提示: 请检查 Streamlit 控制台中的 Secrets 配置是否正确，且项目名 'welding-rag-system' 是否完全一致。")

if __name__ == "__main__":
    main()
