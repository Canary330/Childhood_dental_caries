export {};

// 简单声明 App 和 Page 命名空间，防止 ts 找不到
// 实际类型由 uni-app 提供，这里仅用于避免编辑器报错
declare namespace App {
    interface AppInstance {}
}

declare namespace Page {
    interface PageInstance {}
}

declare module "vue" {
  type Hooks = App.AppInstance & Page.PageInstance;
  interface ComponentCustomOptions extends Hooks {}
}