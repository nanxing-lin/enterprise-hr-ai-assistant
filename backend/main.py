from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import io
import requests
import json

app = FastAPI(title="ChatBI 后端 (Function Calling版)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⚠️ 换成你的真实 DeepSeek API Key
API_KEY = "sk-请输入你真实的api"

# 全局变量，暂存当前用户的数据
current_df = None


class ChatRequest(BaseModel):
    question: str


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    global current_df
    contents = await file.read()
    try:
        if file.filename.endswith('.csv'):
            current_df = pd.read_csv(io.BytesIO(contents))
        else:
            current_df = pd.read_excel(io.BytesIO(contents))
        return {"message": f"解析成功！共 {len(current_df)} 行数据。"}
    except Exception as e:
        return {"message": f"文件解析失败：{str(e)}"}


# =========================================================
# 核心一：定义本地的安全工具函数（AI 只能调用这些）
# =========================================================
def calculate_column_sum(column_name: str):
    """计算某一列的总和"""
    if current_df is None: return "没有数据"
    if column_name not in current_df.columns: return f"错误：列名 {column_name} 不存在"
    return str(current_df[column_name].sum())


def find_max_record(column_name: str, target_column: str):
    """找出某一列最大值对应的一行中，另一列的值。例如：找出销售额最高的那天日期"""
    if current_df is None: return "没有数据"
    if column_name not in current_df.columns or target_column not in current_df.columns:
        return "错误：列名不存在"
    idx = current_df[column_name].idxmax()
    return str(current_df.loc[idx, target_column])


# =========================================================
# 核心二：告诉大模型，我们有哪些工具（Function Calling 菜单）
# =========================================================
tools = [
    {
        "type": "function",
        "function": {
            "name": "calculate_column_sum",
            "description": "计算数据表中某列数字的总和，适用于求总销售额、总利润等。",
            "parameters": {
                "type": "object",
                "properties": {
                    "column_name": {"type": "string", "description": "需要求和的列名"}
                },
                "required": ["column_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "find_max_record",
            "description": "找出某列最大值对应另一列的信息。例如：找最高销售额对应的日期。",
            "parameters": {
                "type": "object",
                "properties": {
                    "column_name": {"type": "string", "description": "用来比较最大值的列，例如'销售额'"},
                    "target_column": {"type": "string", "description": "想要返回的信息所在的列，例如'日期'"}
                },
                "required": ["column_name", "target_column"]
            }
        }
    }
]


# =========================================================
# 核心三：Chat 接口（包含两次调用大模型的 Agent 流程）
# =========================================================
@app.post("/chat")
def chat_with_data(req: ChatRequest):
    global current_df
    if current_df is None:
        return {"answer": "请先上传一份 Excel 或 CSV 数据文件。"}

    columns_info = str(list(current_df.columns))
    print(f"用户提问：{req.question}，当前表头：{columns_info}")

    url = "https://api.deepseek.com/chat/completions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}

    # 第一步：把问题和工具清单发给大模型
    messages = [
        {"role": "system",
         "content": f"你是一个数据分析助手。用户的数据表包含这些列：{columns_info}。请根据用户问题调用合适的工具。"},
        {"role": "user", "content": req.question}
    ]

    data = {
        "model": "deepseek-chat",
        "messages": messages,
        "tools": tools,
        "temperature": 0.1
    }

    try:
        # 第一次请求：大模型会思考，并决定要不要调用工具
        response = requests.post(url, headers=headers, json=data, timeout=30)
        response_data = response.json()["choices"][0]["message"]

        # 检查大模型是否决定调用工具 (Tool Calls)
        if "tool_calls" in response_data and response_data["tool_calls"]:
            tool_call = response_data["tool_calls"][0]
            function_name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])

            print(f"🤖 AI 决定调用工具：{function_name}，参数：{arguments}")

            # 后端根据 AI 的指令，执行本地安全的函数
            if function_name == "calculate_column_sum":
                result = calculate_column_sum(arguments.get("column_name"))
            elif function_name == "find_max_record":
                result = find_max_record(arguments.get("column_name"), arguments.get("target_column"))
            else:
                result = "未知的函数"

            print(f"⚙️ 工具计算结果：{result}")

            # 第二步：把大模型决定调用的工具、以及计算结果，再次发给大模型
            # 这就像是员工查到了数据，把数据汇报给老板，老板再总结成一段话
            messages.append(response_data)  # 把 AI 刚才的调用意图加进去
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": result
            })

            # 第二次请求：让大模型根据计算结果，生成自然语言回答
            data["messages"] = messages
            data.pop("tools")  # 第二次不用再发工具菜单了
            final_response = requests.post(url, headers=headers, json=data, timeout=30)
            final_answer = final_response.json()["choices"][0]["message"]["content"]

            return {"answer": final_answer}

        else:
            # 如果大模型觉得不需要工具（比如问“你好”），直接返回回答
            return {"answer": response_data["content"]}

    except Exception as e:
        print(f"❌ 报错：{e}")
        return {"answer": f"AI 接口调用失败：{e}"}
 # ⚠️ 注意：从这里开始，必须顶格写！没有任何缩进！
app.mount("/assets", StaticFiles(directory="dist/assets"), name="assets")

@app.get("/")
def serve_frontend():
 return FileResponse("dist/index.html")





