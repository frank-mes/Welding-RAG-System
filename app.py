import streamlit as st
import google.generativeai as genai
from github import Github
import datetime
import time
import random
from itertools import cycle

# ==========================================
# 1. SERVICE LAYER (智能引擎层)
# ==========================================
class WeldingService:
    def __init__(self, api_keys):
        """
        api_keys: 传入一个列表，例如 ["key1", "key2"]
        """
        self.api_enabled = False
        self.model_name = "None"
        self.working_keys = []
        
        if not api_keys:
            return

        # 过滤并验证 API Keys
        for key in api_keys:
            if len(key.strip()) > 10:
                self.working_keys.append(key.strip())
        
        if self.working_keys:
            # 创建 Key 轮询器
            self.key_cycle = cycle(self.working_keys)
            self._reconfigure_engine()

    def _reconfigure_engine(self):
        """切换 API Key 并重新配置模型"""
        current_key = next(self.key_cycle)
        try:
            genai.configure(api_key=current_key)
            # 自动探测最新可用模型
            models = [m.name for m in genai.list_models() 
                     if 'generateContent' in m.supported_generation_methods]
            
            priority = ['models/gemini-2.0-flash', 'models/gemini-1.5-flash', 'models/gemini-pro']
            self.model_name = next((p for p in priority if p in models), models[0] if models else None)
            
            if self.model_name:
                self.model = genai.GenerativeModel(self.model_name)
                self.api_enabled = True
        except Exception as e:
            st.sidebar.error(f"❌ Key 初始化失败: {str(e)[:50]}")

    def get_solution(self, material, defect):
        if not self.api_enabled:
            return self.get_mock_response(material, defect)

        max_retries = len(self.working_keys) * 2  # 根据 Key 的数量决定重试次数
        wait_time = 5 
        
        prompt = f"""你是一位资深国际焊接工程师(IWE)。
针对材料【{material}】的【{defect}】缺陷进行深度分析。
要求包含：焊接性分析、成因(微观组织)、预热/层间/后热参数、推荐焊材、保护气比例。
请用专业 Markdown 格式输出。"""

        for i in range(max_retries):
            try:
                # 随机微小延迟，错开高并发请求
                time.sleep(random.uniform(0.5, 1.5)) 
                
                response = self.model.generate_content(prompt)
                
                # 安全提取：防止由于 Gemini 安全过滤导致的 ValueError
                try:
                    return response.text
                except ValueError:
                    return f"⚠️ **AI 警告**：内容因安全策略被拦截，请尝试更专业的术语表述。\n\n{self.get_mock_response(material, defect)}"
                
            except Exception as e:
                err_str = str(e)
                # 如果触发 429 频率限制，尝试轮换 Key
                if "429" in err_str:
                    st.warning(f"🔄 节点繁忙，正在尝试切换备用引擎 (尝试 {i+1}/{max_retries})...")
                    self._reconfigure_engine() # 切换 Key
                    time.sleep(wait_time)
                    wait_time += 5
                    continue
                else:
                    st.error(f"❌ 引擎异常: {err_str[:100]}")
                    break
        
        return self.get_mock_response(material, defect)

    def get_mock_response(self, material, defect):
        return f"""### 🛡️ 专家建议 (本地专家库)
**当前 AI 引擎响应超时或受到限流，已自动匹配标准工艺预案：**

1. **成因分析 ({material})**：
   - 该材料在焊接过程中，{defect} 通常与热循环控制、氢致裂纹敏感性或低熔点共晶物偏析有关。
2. **推荐工艺参数**：
   - **预热温度**：150°C - 200°C（具体视板厚而定）。
   - **焊接能量**：建议采用小电流、多层多道焊，严格控制线能量。
   - **后热处理**：焊后立即进行 250°C x 2h 消氢处理。
3. **焊接材料**：
   - 建议选用与母材匹配的低氢型焊材，并严格执行烘干工艺。"""

# ==========================================
# 2. DATA LAYER (GitHub 存档)
# ==========================================
class WeldingDAO:
    def __init__(self, token, repo_name):
        self.valid = False
        if token and repo_name:
            try:
                self.gh = Github(token)
                self.repo = self.gh.get_user().get_repo(repo_name)
                self.valid = True
            except:
                pass

    def save_record(self, material, solution):
        if not self.valid: return "⚠️ GitHub 存档未配置"
        
        path = f"solutions/{material}_{datetime.date.today()}.md"
        content = f"# 焊接诊断报告\n\n- 生成时间: {datetime.datetime.now()}\n- 材料: {material}\n\n---\n\n{solution}"
        
        try:
            try:
                item = self.repo.get_contents(path)
                self.repo.update_file(path, f"Update {material}", content, item.sha)
                return "✅ 云端档案已更新"
            except:
                self.repo.create_file(path, f"Create {material}", content)
                return "✅ 云端档案已新建"
        except Exception as e:
            return f"❌ 同步失败: {str(e)[:30]}"

# ==========================================
# 3. UI LAYER (界面与缓存控制)
# ==========================================
@st.cache_resource
def get_service(keys_str):
    # 将输入的逗号分隔的 Key 字符串转为列表
    keys = keys_str.split(",") if keys_str else []
    return WeldingService(keys)

def main():
    st.set_page_config(page_title="焊接RAG专家系统", page_icon="👨‍🏭")
    
    st.title("🛡️ 焊接缺陷 AI 诊断中心")
    st.caption("AI 辅助决策系统 | 工业级双引擎版本")

    # 1. 获取 Secrets (支持单 Key 或逗号分隔的多 Key)
    gemini_keys_raw = st.secrets.get("GEMINI_KEY", "")
    gh_token = st.secrets.get("GH_TOKEN", "")
    repo_name = st.secrets.get("REPO_NAME", "welding-rag-system")

    # 2. 初始化引擎
    svc = get_service(gemini_keys_raw)
    
    # 侧边栏
    with st.sidebar:
        st.header("系统状态")
        if svc.api_enabled:
            st.success(f"在线：{svc.model_name}")
            st.info(f"可用备用节点数: {len(svc.working_keys)}")
        else:
            st.error("离线：AI 引擎未就绪")
        st.divider()
        st.markdown("⚠️ **提示**：如果频繁出现冷却，请在 Secrets 中添加更多 API Key。")

    # 3. 主界面布局
    with st.container(border=True):
        c1, c2 = st.columns(2)
        material = c1.text_input("材料牌号", placeholder="例如: S32205")
        defect = c2.text_input("缺陷类型", placeholder="例如: 夹杂")

    if st.button("开始 AI 推理诊断", type="primary", use_container_width=True):
        if not material or not defect:
            st.warning("请完整填写信息。")
            return

        # 进度展示
        with st.status("正在调取云端专家知识库...", expanded=True) as status:
            solution = svc.get_solution(material, defect)
            status.update(label="诊断报告生成完毕！", state="complete")

        st.markdown("---")
        st.subheader("💡 专家建议方案")
        st.markdown(solution)

        # 4. 执行异步存档
        if gh_token:
            dao = WeldingDAO(gh_token, repo_name)
            msg = dao.save_record(material, solution)
            st.toast(msg)

if __name__ == "__main__":
    main()
