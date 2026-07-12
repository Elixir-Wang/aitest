declare module "simple-mind-map" {
  type MindMapNode = {
    getData(key: string): unknown;
    active(): void;
  };

  type MindMapOptions = {
    el: HTMLElement;
    data: unknown;
    layout?: string;
    readonly?: boolean;
    fit?: boolean;
    mousewheelAction?: string;
    enableFreeDrag?: boolean;
    textAutoWrapWidth?: number;
    expandBtnSize?: number;
    expandBtnStyle?: {
      color?: string;
      fill?: string;
      fontSize?: number;
      strokeColor?: string;
    };
    nodeTextEditZIndex?: number;
    maxTag?: number;
    rainbowLinesConfig?: {
      open: boolean;
      colorsList?: string[];
    };
    themeConfig?: Record<string, unknown>;
  };

  type MindMapPlugin = {
    new (options: { mindMap: MindMap }): unknown;
    instanceName: string;
  };

  export default class MindMap {
    constructor(options: MindMapOptions);
    static usePlugin(plugin: MindMapPlugin, options?: Record<string, unknown>): void;
    view: {
      scale: number;
      fit(): void;
      narrow(): void;
      enlarge(): void;
    };
    renderer: { findNodeByUid(uid: string): MindMapNode | null };
    on(event: "node_tree_render_end", listener: () => void): void;
    on(event: "node_click", listener: (node: MindMapNode) => void): void;
    on(event: "scale", listener: (scale: number) => void): void;
    off(event: "node_tree_render_end", listener: () => void): void;
    off(event: "node_click", listener: (node: MindMapNode) => void): void;
    off(event: "scale", listener: (scale: number) => void): void;
    resize(): void;
    destroy(): void;
  }
}

type SimpleMindMapInstance = import("simple-mind-map").default;

declare module "simple-mind-map/src/plugins/RainbowLines.js" {
  const RainbowLines: {
    new (options: { mindMap: SimpleMindMapInstance }): unknown;
    instanceName: "rainbowLines";
  };
  export default RainbowLines;
}
