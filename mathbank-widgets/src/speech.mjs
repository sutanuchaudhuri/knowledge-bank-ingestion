// Turn tutor markdown/LaTeX into text a TTS voice can read naturally ("\angle ABC" -> "angle A B C").
// Pure and deterministic; used by SpeakButton before sending text to /api/voice/tts.

export const MAX_SPEAK_CHARS = 1200;

const WORDS = [
  [/\\angle\s*/g, "angle "], [/\\triangle\s*/g, "triangle "], [/\\cdot|\\times/g, " times "],
  [/\\le\b|\\leq\b/g, " is at most "], [/\\ge\b|\\geq\b/g, " is at least "], [/\\ne\b|\\neq\b/g, " is not equal to "],
  [/\\perp\b/g, " is perpendicular to "], [/\\parallel\b/g, " is parallel to "], [/\\cong\b/g, " is congruent to "],
  [/\\sim\b/g, " is similar to "], [/\\pi\b/g, "pi"], [/\\theta\b/g, "theta"], [/\\alpha\b/g, "alpha"],
  [/\\beta\b/g, "beta"], [/\\gamma\b/g, "gamma"], [/\\infty\b/g, "infinity"], [/\\pm\b/g, " plus or minus "],
  [/\\Rightarrow\b|\\implies\b/g, " implies "], [/\\iff\b/g, " if and only if "], [/\\therefore\b/g, " therefore "],
  [/\\in\b/g, " in "], [/\^\\circ|°/g, " degrees"],
];

// Spell short upper-case point names letter by letter so "PA" is read "P A", not a word.
const spellPoints = (s) => s.replace(/\b([A-Z]{2,4})\b/g, (m) => m.split("").join(" "));

export function speakableText(markdown) {
  let s = String(markdown || "");
  s = s.replace(/```[\s\S]*?```/g, " ").replace(/!\[[^\]]*\]\([^)]*\)/g, " ").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1");
  s = s.replace(/\$\$([\s\S]+?)\$\$|\$([^$]+)\$|\\\(([\s\S]+?)\\\)|\\\[([\s\S]+?)\\\]/g,
    (_m, a, b, c, d) => ` ${mathToSpeech(a ?? b ?? c ?? d ?? "")} `);
  s = s.replace(/[*_#>`|]+/g, " ").replace(/\s+/g, " ").trim();
  return s.length > MAX_SPEAK_CHARS ? `${s.slice(0, MAX_SPEAK_CHARS).replace(/\s+\S*$/, "")} …` : s;
}

export function mathToSpeech(tex) {
  let s = String(tex);
  for (let i = 0; i < 3; i += 1) {
    s = s.replace(/\\frac\{([^{}]*)\}\{([^{}]*)\}/g, " $1 over $2 ").replace(/\\sqrt\{([^{}]*)\}/g, " square root of $1 ")
      .replace(/\\overline\{([^{}]*)\}/g, " segment $1 ").replace(/\\overset\{\\frown\}\{([^{}]*)\}/g, " arc $1 ");
  }
  s = s.replace(/\^\{?2\}?(?![\d{])/g, " squared").replace(/\^\{?3\}?(?![\d{])/g, " cubed");
  for (const [re, word] of WORDS) s = s.replace(re, word);
  s = s.replace(/\^\{([^{}]*)\}|\^(\w)/g, " to the power $1$2 ").replace(/_\{([^{}]*)\}|_(\w)/g, " sub $1$2 ");
  s = s.replace(/=/g, " equals ").replace(/\+/g, " plus ").replace(/(?<=\s|^)-(?=\s)/g, " minus ")
    .replace(/</g, " is less than ").replace(/>/g, " is greater than ");
  s = s.replace(/\\[a-zA-Z]+/g, " ").replace(/[{}\\]/g, " ");
  return spellPoints(s).replace(/\s+/g, " ").trim();
}
