export interface Activity {
  alive: boolean;
  message: string;
  checked_markets: number;
  expected_markets: number;
  last_checked_closed_bar_utc: string | null;
}

export function activityText(
  activity: Activity | undefined,
  format: (value: string) => string,
): string {
  if (!activity) return "Kerzenverarbeitung noch nicht bestätigt.";
  const checked = activity.last_checked_closed_bar_utc
    ? ` · Zuletzt verarbeitet: ${format(activity.last_checked_closed_bar_utc)}`
    : " · Noch keine vollständige Kerzenverarbeitung bestätigt";
  return `${activity.alive ? "Bot verarbeitet aktuelle Daten" : "Aktivität prüfen"}`
    + ` · ${activity.checked_markets}/${activity.expected_markets} Märkte${checked}. `
    + activity.message + " Ein laufender Paper-Bot startet keinen Echtgeldtest automatisch.";
}
