# Prompt：生成可交互函数调用流程图（单页 HTML）

## 任务

阅读我提供的项目源码，生成一个单页 HTML 文件，包含可交互的函数调用流程图。
节点支持点击跳转到 VS Code 对应文件行号。

---

## 流程图要求

1. 分析项目的核心调用链（从入口函数到底层实现），覆盖主流程
2. 每个节点显示：函数名 + 所在文件名（不需要完整路径）
3. 用不同颜色区分层次（如：路由层 / 业务层 / 服务层 / 工具层）
4. 节点之间的箭头标注关键传参或触发条件（可选）

---

## 跳转功能要求

- 每个节点绑定点击事件，点击后在 VS Code 中打开对应文件并跳转到该函数所在行
- 链接格式：`vscode://file/{文件绝对路径}:{行号}`
- **必须先用工具搜索每个函数的准确行号，禁止猜测**
- **不要使用 Mermaid 内置的 `click` 指令**（该指令在 VS Code Simple Browser 的 iframe 安全策略下会被拦截）
- 改用 JS 在 SVG 渲染完成后，通过 `el.addEventListener('click', ...)` 手动绑定，触发方式为 `window.location.href = url`

---

## 缩放/平移要求

- 引入 `svg-pan-zoom@3.6.1`（CDN）实现鼠标滚轮缩放、拖拽平移
- 初始化参数：`preventMouseEventsDefault: false`（必须，否则节点点击事件会被拦截）
- 提供右上角 ＋ / － / 重置 三个按钮
- 支持键盘快捷键：`+` 放大，`-` 缩小，`0` 重置
- 初始化后立即调用 `pz.fit()` + `pz.center()`，确保图表居中

---

## SVG 空白修复（重要）

Mermaid 生成的 SVG 存在右侧大片空白问题，**必须**在渲染后执行以下修复：

```js
// 1. 移除 Mermaid 附加的 style="max-width:Xpx" 和 width/height 属性
svgEl.removeAttribute('width');
svgEl.removeAttribute('height');
svgEl.removeAttribute('style');
svgEl.style.width = '100%';
svgEl.style.height = '100%';

// 2. 用 getBBox() 重算 viewBox，裁掉多余空白
const rootG = svgEl.querySelector('g');
if (rootG) {
  const bb = rootG.getBBox();
  const pad = 24;
  svgEl.setAttribute('viewBox',
    `${bb.x - pad} ${bb.y - pad} ${bb.width + pad * 2} ${bb.height + pad * 2}`);
}
```

---

## Mermaid 渲染方式（重要）

- 使用 `mermaid.render()` 异步 API，**不要**用 `startOnLoad: true`（会导致点击绑定时机错误）
- 正确流程：

```js
mermaid.initialize({ startOnLoad: false, securityLevel: 'loose', ... });

document.addEventListener('DOMContentLoaded', async () => {
  const { svg } = await mermaid.render('unique-id', DIAGRAM_SOURCE);
  wrap.innerHTML = svg;
  const svgEl = wrap.querySelector('svg');
  // 修复 viewBox → 绑定点击 → 初始化 pan-zoom
});
```

- `securityLevel: 'loose'` 必须设置，否则 SVG 内 JS 无法执行

---

## HTML 技术要求

- 使用 Mermaid.js v10（CDN）绘制流程图
- 使用 svg-pan-zoom v3.6.1（CDN）实现缩放平移
- 页面包含标题、图例（颜色说明）、简短说明文字
- 样式：背景浅色（`#f0f4f8`），节点有 hover 发光效果（`drop-shadow`）
- 鼠标悬停节点时显示完整文件路径 tooltip
- 纯静态单文件，无需任何服务器

---

## 本地预览方式

生成文件后，提示用户用以下命令启动本地服务器（Simple Browser 不支持直接打开本地 `file://`）：

```bash
python3 -m http.server 8765 -d {文件所在目录}
```

然后在 VS Code 中：`Ctrl+Shift+P` → `Simple Browser: Show` → `http://localhost:8765/{文件名}.html`

> ⚠️ 节点跳转功能只在 VS Code Simple Browser（Electron webview）中有效，系统浏览器中 `vscode://` 协议无法触发。

---

## 输出

- 输出完整 HTML 文件，保存到指定路径
- 同时在项目 `.vscode/tasks.json` 中添加一个后台任务自动启动 HTTP 服务器：

```json
{
  "label": "Serve flowchart",
  "type": "shell",
  "command": "fuser -k {PORT}/tcp 2>/dev/null; python3 -m http.server {PORT} -d ${workspaceFolder}/{目录}",
  "isBackground": true,
  "problemMatcher": []
}
```

注意 `command` 开头的 `fuser -k` 是为了**自动清理已占用端口**，避免重复运行时报 `Address already in use`。
