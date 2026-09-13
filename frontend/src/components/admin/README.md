# `components/admin/` 该怎么读

这个目录原先叫"共享管理组件"，但研究文档 F7 指出它**名不副实**：5 个组件里 4 个只有
一个消费者。于是接手的人会误以为它们都被多处依赖，既不敢改、也不敢删。

结构优化阶段 3 处理后的现状（引用者数量为**实测**，2026-09-14）：

## 顶层 = 真正被多页共享

| 组件 | 引用者数 | 说明 |
| --- | --- | --- |
| `DataTable.vue` | **8** | F1 之前只有 `AuditPage` 1 个消费者（"假共享"）。已升级为真原语并落地 11/12 张管理页表格，见文件头注释 |
| `PageHeader.vue` | **10** | 一直是共享的 |

## `page-parts/` = 单页专用

| 组件 | 唯一消费者 |
| --- | --- |
| `SettingsSection.vue` | `views/admin/SecurityPage.vue` |
| `VenueCredentialCard.vue` | `views/admin/SecurityPage.vue` |
| `DangerZone.vue` | `views/admin/RiskPage.vue` |

放进子目录是**刻意的**：让"单页专用"这件事写在路径上，而不是靠读者去数引用。
F7 的另一种解法（推广）对这三个组件目前**不成立**，理由见下。

## `SettingsSection` 为什么没有"推广"

实测有 **9 个管理页**在手工重写"带标题的卡片"：`AboutPage` `AdminSysPage` `AgentsPage`
`BackupPage` `DecisionsPage` `EvolutionPage` `GatewayPage` `NotifyPage` `PluginsPage`。

看起来很该推广，但逐页比对后**它们不是同一个形状**：

- `SettingsSection`：`<section>` + `<header px-4 py-3>`（标题 + description + actions 槽）+ `<div p-4>` 两段式
- 手写版：整卡 `p-4 sm:p-5` + 内联 header（`flex items-center justify-between pb-3 mb-3 border-b`），
  且**标题里带图标、header 里塞内联徽标与页面专属副文本**（例：`AboutPage` 的
  `INFO/OPEN SOURCE`、`AdminSysPage` 的 `KeyRound` + 当前账号名）

要吃掉这些变体，得给组件加图标槽、徽标槽、header 变体 —— 那是**设计改动**，
会让 9 个上线页面的外观发生变化，必须目视评审。故本轮**不做**，保持手写原样。

## 顺带发现（不在本轮批准的计划内，仅记录）

以下 10 个组件在 `src/` 里**实测 0 个引用者**（已排除路径别名导致的误判）：

    components/base/       BaseSwitch · BaseSparkline · BaseDrawer · BaseDialog ·
                           BaseTabs · CopyButton
    components/dashboard/  VenueAccountCard · DataStatus · SettingsPopover · FactorDrawer

清理它们属于删除操作，且需先确认不是动态引用/预留；按仓库纪律（破坏性操作先问）
**未动**，记录在此供后续决策。
