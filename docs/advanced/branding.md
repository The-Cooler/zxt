# 品牌自定义

自学通 支持品牌自定义，包括 Logo、组织名称、版权信息、协议链接等，方便个人使用时调整展示信息。

## 品牌信息配置

### 步骤 1：复制模板文件

```bash
cp backend/package/zixuetong/config/static/info.template.yaml backend/package/zixuetong/config/static/info.local.yaml
```

### 步骤 2：编辑品牌信息

在 `backend/package/zixuetong/config/static/info.local.yaml` 中配置你的品牌信息：

- 应用名称
- 组织名称
- Logo
- 版权信息
- 用户协议/隐私协议链接

### 步骤 3：指定配置文件

在 `.env` 中指定配置文件路径：

```env
ZIXUETONG_BRAND_FILE_PATH=backend/package/zixuetong/config/static/info.local.yaml
```

::: tip 配置优先级
`info.local.yaml` > `info.template.yaml`（默认）
:::

## 协议链接配置

系统支持从品牌配置中读取用户协议与隐私协议链接，供页脚或相关入口展示。

### 配置项

在 `backend/package/zixuetong/config/static/info.local.yaml` 的 `footer` 下新增以下字段：

```yaml
footer:
  copyright: "© your org 2026"
  user_agreement_url: "/protocols/user-agreement.template.html"
  privacy_policy_url: "/protocols/privacy-policy.template.html"
```

### 显示规则

- 当 `user_agreement_url` 和 `privacy_policy_url` 有值时，相关页面可展示协议链接。
- 任一字段为空时，对应链接不会展示。

### 协议模板文件

系统默认提供两个 HTML 模板文件：

- `web/public/protocols/user-agreement.template.html`
- `web/public/protocols/privacy-policy.template.html`

你可以直接编辑这两个文件中的协议内容，并替换占位符（如 `{{ORG_NAME}}`、`{{PRODUCT_NAME}}`、`{{EFFECTIVE_DATE}}`）。

如果你有自己的协议页面，也可以将 `user_agreement_url` 和 `privacy_policy_url` 指向自定义路径或外部链接。

### Icon 定制

系统预设了多种 Icon，如需更多图标，可以从 `lucide-vue-next` 中引入。

## 样式定制

系统支持完整的主题色定制。配置文件位于 `web/src/assets/css/base.css`，以及 `web/src/assets/css/base.dark.css`：

```css
:root {
  --main-color: #1890ff;        /* 主色调 */
  --main-1000: #f0f2f5;          /* 色板 */
  --main-900: #e6f7ff;           /* 色板 */
  /* ... 其他色板 */
}
```

修改配色变量后，界面会实时更新，无需重启服务。

此外，`web/src/stores/theme.js` 中的 `colorPrimary` 也需要同步修改。
