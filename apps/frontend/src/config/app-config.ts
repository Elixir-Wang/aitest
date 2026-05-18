import packageJson from "../../package.json";

const currentYear = new Date().getFullYear();

export const APP_CONFIG = {
  name: "AI 测试系统",
  version: packageJson.version,
  copyright: `© ${currentYear}, AI 测试系统.`,
  meta: {
    title: "AI 测试系统",
    description:
      "AI 测试系统用于需求分析、站点探索、知识库生成、测试用例生成、UI 自动化执行和报告闭环。",
  },
};
