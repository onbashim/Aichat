import { defineRailway, github, postgres, preserve, project, service } from "railway/iac";

export default defineRailway(() => {
  const db = postgres("Postgres");

  const app = service("telegram-ai-os", {
    source: github("onbashim/Aichat", { branch: "main" }),
    healthcheck: "/health",
    healthcheckTimeout: 120,
    env: {
      DATABASE_URL: db.env.DATABASE_URL,
      TELEGRAM_BOT_TOKEN: preserve(),
      TELEGRAM_OWNER_ID: preserve(),
      TELEGRAM_WEBHOOK_SECRET: preserve(),
      OPENAI_API_KEY: preserve(),
      OPENAI_MODEL: "gpt-5.6-terra",
      APP_ENV: "production",
      LOG_LEVEL: "INFO",
      AI_AUTOMATION_ENABLED: "false",
      AUTOPILOT_ENABLED: "false",
    },
  });

  return project("Telegram AI OS", { resources: [db, app] });
});
