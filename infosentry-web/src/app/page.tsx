import { redirect } from "next/navigation";

/**
 * 首页重定向到 Goals 页面
 */
export default function HomePage() {
  redirect("/goals");
}
