# find-skills — WorkBuddy 环境适配

本技能源自 `vercel-labs/skills`（https://github.com/vercel-labs/skills/tree/main/skills/find-skills）。
在 WorkBuddy 中，`npx skills` 可能与本地技能目录不互通，**优先使用内置工具**完成同样的动作：

- **搜索**：`search_and_install_skills`（action=`search`，keywords 传关键词）
- **安装**：`search_and_install_skills`（action=`install`，skill_names 传搜索结果里的精确 name）
- **查看已装技能**：`skill_management`（action=`list`）

只有当内置商店里确实搜不到、而 skills.sh / GitHub 上有明确目标时，才回退到 `npx skills find` 与
`npx skills add`；此时安装结果落在 `~/.claude/skills/`，需要手动复制到 `~/.workbuddy/skills/<name>/`
才会被 WorkBuddy 加载。
