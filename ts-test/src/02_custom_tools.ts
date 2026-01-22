/**
 * 工具示例：如何在 Agent 中使用自定义工具（MCP SDK 工具）
 * TypeScript 版本 - 对应 Python 版本的 02_custom_tools.py
 */

import { query, createSdkMcpServer, tool } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";
import * as dotenv from "dotenv";

// 加载环境变量（从父目录的 .env 文件）
import * as path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
dotenv.config({ path: path.resolve(__dirname, "../../.env") });

// ============================================
// 定义计算器工具
// ============================================

// 加法工具
const addTool = tool(
  "add",
  "将两个数字相加",
  {
    a: z.number().describe("第一个数字"),
    b: z.number().describe("第二个数字"),
  },
  async (args) => {
    const result = args.a + args.b;
    return {
      content: [
        {
          type: "text" as const,
          text: `计算结果: ${args.a} + ${args.b} = ${result}`,
        },
      ],
    };
  }
);

// 乘法工具
const multiplyTool = tool(
  "multiply",
  "将两个数字相乘",
  {
    a: z.number().describe("第一个数字"),
    b: z.number().describe("第二个数字"),
  },
  async (args) => {
    const result = args.a * args.b;
    return {
      content: [
        {
          type: "text" as const,
          text: `计算结果: ${args.a} × ${args.b} = ${result}`,
        },
      ],
    };
  }
);

// 减法工具
const subtractTool = tool(
  "subtract",
  "将两个数字相减",
  {
    a: z.number().describe("第一个数字"),
    b: z.number().describe("第二个数字"),
  },
  async (args) => {
    const result = args.a - args.b;
    return {
      content: [
        {
          type: "text" as const,
          text: `计算结果: ${args.a} - ${args.b} = ${result}`,
        },
      ],
    };
  }
);

// 除法工具
const divideTool = tool(
  "divide",
  "将两个数字相除",
  {
    a: z.number().describe("被除数"),
    b: z.number().describe("除数"),
  },
  async (args) => {
    if (args.b === 0) {
      return {
        content: [
          {
            type: "text" as const,
            text: "错误：除数不能为零",
          },
        ],
        isError: true,
      };
    }
    const result = args.a / args.b;
    return {
      content: [
        {
          type: "text" as const,
          text: `计算结果: ${args.a} ÷ ${args.b} = ${result}`,
        },
      ],
    };
  }
);

// ============================================
// 创建 MCP 服务器并运行查询
// ============================================

async function main() {
  console.log("正在创建计算器 MCP 服务器...");

  // 创建 SDK MCP 服务器
  const calculatorServer = createSdkMcpServer({
    name: "calculator",
    version: "1.0.0",
    tools: [addTool, multiplyTool, subtractTool, divideTool],
  });

  console.log("正在询问 Claude 进行计算...\n");

  try {
    // 使用 query() 函数查询
    const response = query({
      prompt: "请计算 15.5 乘以 3.2 的结果是多少？",
      options: {
        systemPrompt: "你是一个数学助手。使用提供的计算器工具来进行计算。",
        mcpServers: {
          calculator: calculatorServer,
        },
        // 允许使用这些工具（使用 MCP 工具命名格式）
        allowedTools: [
          "mcp__calculator__add",
          "mcp__calculator__multiply",
          "mcp__calculator__subtract",
          "mcp__calculator__divide",
        ],
      },
    });

    // 处理消息流
    for await (const message of response) {
      // 使用 any 类型来绕过 SDK 类型定义的限制
      const msg = message as any;

      switch (msg.type) {
        case "assistant":
          // 打印助手的回复
          // content 可能是 string 或者 array
          if (typeof msg.content === "string") {
            if (msg.content.trim()) {
              console.log("Agent 回复：");
              console.log(msg.content);
            }
          } else if (Array.isArray(msg.content)) {
            const textBlocks = msg.content.filter((b: any) => b.type === "text" && b.text?.trim());
            if (textBlocks.length > 0) {
              console.log("Agent 回复：");
              for (const block of textBlocks) {
                console.log(block.text);
              }
            }
          } else if (msg.message?.content) {
            // 备选：从 message.content 获取
            const content = msg.message.content;
            if (typeof content === "string" && content.trim()) {
              console.log("Agent 回复：");
              console.log(content);
            } else if (Array.isArray(content)) {
              const textBlocks = content.filter((b: any) => b.type === "text" && b.text?.trim());
              if (textBlocks.length > 0) {
                console.log("Agent 回复：");
                for (const block of textBlocks) {
                  console.log(block.text);
                }
              }
            }
          }
          break;

        case "user":
          // 工具调用结果（以 user 消息形式返回）
          if (msg.tool_use_result) {
            console.log("\n[工具执行结果]");
            for (const result of msg.tool_use_result) {
              if (result.type === "text") {
                console.log(`  ${result.text}`);
              }
            }
          }
          break;

        case "system":
          // 系统消息
          if (msg.subtype === "init") {
            console.log(`[系统] 会话已初始化，会话ID: ${msg.session_id || "N/A"}`);
          } else if (msg.subtype === "completion") {
            console.log("\n[系统] 任务完成");
          }
          break;

        case "result":
          // 处理结果消息
          if (msg.isError || msg.is_error) {
            console.log(`\n[错误] ${msg.result}`);
          } else {
            console.log(`\n[完成] 耗时: ${msg.durationMs || msg.duration_ms || "N/A"}ms`);
            if (msg.totalCostUsd || msg.total_cost_usd) {
              const cost = msg.totalCostUsd || msg.total_cost_usd;
              console.log(`[成本] $${cost.toFixed(6)}`);
            }
          }
          break;

        default:
          // 其他消息类型（tool_progress, stream_event, auth_status 等）
          // console.log(`[其他] 消息类型: ${msg.type}`, JSON.stringify(msg, null, 2));
          break;
      }
    }
  } catch (error) {
    console.error("查询出错:", error);
    throw error;
  }
}

// 运行主函数
main().catch(console.error);
