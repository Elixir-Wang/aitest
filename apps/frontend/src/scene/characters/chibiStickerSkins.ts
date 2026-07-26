/** Spine Chibi Stickers 可用皮肤（9 套，16 人会轮换复用） */
export const CHIBI_CHARACTER_SKINS = [
  "misaki",
  "erikari",
  "nate",
  "harri",
  "luke",
  "soeren",
  "mario",
  "sinisa",
  "spineboy",
] as const;

export function getChibiSkinName(agentId: string): string {
  let hash = 0;
  for (const character of agentId) {
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  }
  return CHIBI_CHARACTER_SKINS[hash % CHIBI_CHARACTER_SKINS.length] ?? "spineboy";
}
