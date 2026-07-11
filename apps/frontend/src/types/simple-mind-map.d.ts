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
    nodeTextEditZIndex?: number;
    themeConfig?: Record<string, unknown>;
  };

  export default class MindMap {
    constructor(options: MindMapOptions);
    view: { fit(): void };
    renderer: { findNodeByUid(uid: string): MindMapNode | null };
    on(event: "node_tree_render_end", listener: () => void): void;
    on(event: "node_click", listener: (node: MindMapNode) => void): void;
    resize(): void;
    destroy(): void;
  }
}

type SimpleMindMapInstance = import("simple-mind-map").default;
