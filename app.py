import streamlit as st
import google.generativeai as genai
from github import Github
import datetime
import time

# ==========================================
# 1. SERVICE LAYER (具备智能寻址与容错能力)
# ==========================================
class WeldingService:
    def __init__(self, api_key):
        self.api_enabled = False
        self.model_name = "None"
        
        if api_key and len(api_key) > 10:
            try:
                genai.configure(api_key=api_key)
                # 核心修复：自动列出所有可用模型，解决 404 路径问题
                available_models = [m.name for m in genai.list_models() 
                                   if 'generateContent' in m.supported_generation_methods]
                
                # 定义优先级顺序
                priority = ['models/gemini-1.5-flash', 'gemini-1.5-flash', 'models/gemini-pro', 'gemini-pro']
                
                selected_model = None
                for p in priority:
                    if p in available_models:
                        selected_model = p
                        break
                
                # 如果都没匹配到，用列表里第一个
                if not selected_model and available_models:
                    selected_model = available_models[0]
                
                if selected_model:
                    self.model = genai.GenerativeModel(selected_model)
                    self.model_name = selected_model
                    self.api_enabled = True
                    st.sidebar.success(f"已连接引擎: {selected_model}")
                else:
                    st.sidebar.error("❌ 该 Key 未授权任何可用模型")
            except Exception as e:
                st.sidebar.warning(f"⚠️ 引擎初始化失败: {e}")

    def get_solution(self, material, defect):
        if self.api_enabled:
            try:
                # 模拟专家思考的 Prompt
                prompt = (f"你是一位资深的国际焊接工程师(IWE)。请针对材料【{material}】"
                         f"出现的【{defect}】缺陷，提供失效分析及详细的工艺修复建议。"
                         f"请使用 Markdown 格式输出，包含：原因分析、工艺参数调整、焊后检验要求。")
                
                response = self.model.generate_content(prompt)
                return response.text
            except Exception as e:
                if "429" in str(e):
                    st.error("🚨 达到 API 频率限制，进入本地专家库...")
                else:
                    st.error(f"❌ AI 生成失败: {e}")
        
        # 兜底逻辑：如果 API 不可用或报错，返回预设方案
        time.sleep(1.5) 
        return f"### 🛡️ 专家建议 (本地库备份)\n\n**缺陷分析**：针对 {material} 的 {defect} 缺陷，可能是热输入不当导致。\n\n**修复建议**：\n1. 清理坡口油脂与氧化皮；\n2. 严格控制层间温度；\n3. 推荐使用小电流多
        
