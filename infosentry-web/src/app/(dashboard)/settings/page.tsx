"use client";

import { PageHeader } from "@/components/layout";
import { Card, CardContent, CardHeader } from "@/components/ui";
import { useAuth } from "@/contexts/auth-context";

export default function SettingsPage() {
  const { user } = useAuth();

  return (
    <div>
      <PageHeader title="设置" description="管理您的账户和偏好设置" />

      <div className="space-y-6">
        {/* Account */}
        <Card>
          <CardHeader>
            <h2 className="text-base font-semibold text-gray-900">账户信息</h2>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-500 mb-1">
                  邮箱地址
                </label>
                <p className="text-sm font-medium text-gray-900">
                  {user?.email || "-"}
                </p>
              </div>
              <div>
                <label className="block text-sm text-gray-500 mb-1">
                  时区
                </label>
                <p className="text-sm font-medium text-gray-900">
                  {user?.timezone || "Asia/Shanghai"}
                </p>
              </div>
              <div>
                <label className="block text-sm text-gray-500 mb-1">
                  账户状态
                </label>
                <p className="text-sm font-medium text-green-600">
                  {user?.is_active ? "正常" : "已禁用"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Preferences */}
        <Card>
          <CardHeader>
            <h2 className="text-base font-semibold text-gray-900">推送偏好</h2>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-gray-500">
              推送设置在每个目标中单独配置
            </p>
          </CardContent>
        </Card>

        {/* About */}
        <Card>
          <CardHeader>
            <h2 className="text-base font-semibold text-gray-900">关于</h2>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">版本</span>
                <span className="text-gray-900">1.0.0</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">项目</span>
                <span className="text-gray-900">infoSentry</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

