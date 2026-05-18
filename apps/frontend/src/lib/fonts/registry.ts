const systemFont = {
  variable: "--font-system-sans",
  className: "font-sans",
};

const systemMonoFont = {
  variable: "--font-system-mono",
  className: "font-mono",
};

export const fontRegistry = {
  geist: {
    label: "Geist",
    font: systemFont,
  },
  inter: {
    label: "Inter",
    font: systemFont,
  },
  notoSans: {
    label: "Noto Sans",
    font: systemFont,
  },
  nunitoSans: {
    label: "Nunito Sans",
    font: systemFont,
  },
  figtree: {
    label: "Figtree",
    font: systemFont,
  },
  roboto: {
    label: "Roboto",
    font: systemFont,
  },
  raleway: {
    label: "Raleway",
    font: systemFont,
  },
  dmSans: {
    label: "DM Sans",
    font: systemFont,
  },
  publicSans: {
    label: "Public Sans",
    font: systemFont,
  },
  outfit: {
    label: "Outfit",
    font: systemFont,
  },
  geistMono: {
    label: "Geist Mono",
    font: systemMonoFont,
  },
  geistPixelSquare: {
    label: "Geist Pixel Square",
    font: systemFont,
  },
  jetBrainsMono: {
    label: "JetBrains Mono",
    font: systemMonoFont,
  },
  notoSerif: {
    label: "Noto Serif",
    font: systemFont,
  },
  robotoSlab: {
    label: "Roboto Slab",
    font: systemFont,
  },
  merriweather: {
    label: "Merriweather",
    font: systemFont,
  },
  lora: {
    label: "Lora",
    font: systemFont,
  },
  playfairDisplay: {
    label: "Playfair Display",
    font: systemFont,
  },
} as const;

export type FontKey = keyof typeof fontRegistry;

export const fontVars = "";

export const fontOptions = (Object.entries(fontRegistry) as Array<[FontKey, (typeof fontRegistry)[FontKey]]>).map(
  ([key, f]) => ({
    key,
    label: f.label,
    variable: f.font.variable,
  }),
);
