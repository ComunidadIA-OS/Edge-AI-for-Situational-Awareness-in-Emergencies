export type SidebarTab = "status" | "detections" | "weather" | "layers";

export type ViewMode = "2d" | "3d";

export type ConnectionState = "unconfigured" | "connecting" | "online" | "stale" | "offline";

export type ToastVariant = "info" | "success" | "warning" | "error";

export type Toast = {
  id: string;
  message: string;
  variant: ToastVariant;
  duration?: number;
};
