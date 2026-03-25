## ADDED Requirements

### Requirement: 外部 URL 获取必须是 Redirect-Safe 的

任何发起外部 URL 请求的能力 MUST 对目标地址做完整 SSRF 防护，覆盖初始请求和所有重定向跳转。

#### Scenario: 初始 URL 合法但重定向到内网地址

```
Given 系统准备请求一个 http 或 https URL
  And 初始 URL 的 host 属于公共地址
When 远端返回 3xx 并将 Location 指向 private、loopback、link-local、reserved 或 multicast 地址
Then 系统 MUST 拒绝继续请求该跳转目标
  And MUST 将本次请求视为不允许访问
```

### Requirement: 接口层不得直接实例化基础设施依赖

跨模块能力的基础设施实现 MUST 通过依赖注入装配，接口层不得直接 new 具体 infrastructure provider。

#### Scenario: Router 需要使用外部目录或远端 provider

```
Given 某个 HTTP router 需要调用 catalog provider、fetcher factory 或其他基础设施能力
When router 处理请求
Then router MUST 通过 application/infrastructure 依赖注入获取该能力
  And MUST NOT 在路由函数中直接实例化具体 infrastructure 实现
```
