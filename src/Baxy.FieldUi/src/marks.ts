import { Lexer, type Token, type Tokens } from 'marked';

/* The marks of an answer read by marked's lexer (markdown.tsx draws them; this says the words alone, for the captions). */

export const lexer = (text: string): Token[] => new Lexer({ gfm: true, breaks: false }).lex(text);

// CommonMark 2.5 «Entity and numeric character references»: the few a model writes, decoded as text (never as HTML).
const NAMED: Record<string, string> = { amp: '&', lt: '<', gt: '>', quot: '"', apos: '\'', nbsp: '\u00a0' };
export function decoded(text: string): string {
  return text.replace(/&(#x[0-9a-f]{1,6}|#[0-9]{1,7}|[a-z]+);/gi, (whole, name: string) => {
    if (name[0] !== '#') return NAMED[name.toLowerCase()] ?? whole;
    const code = name[1] === 'x' || name[1] === 'X' ? parseInt(name.slice(2), 16) : parseInt(name.slice(1), 10);
    return code > 0 && code <= 0x10ffff ? String.fromCodePoint(code) : whole;
  });
}

function plainInline(tokens: Token[] | undefined): string {
  return (tokens ?? []).map((token) => {
    switch (token.type) {
      case 'strong': case 'em': case 'del': return plainInline((token as Tokens.Strong).tokens);
      case 'codespan': return decoded((token as Tokens.Codespan).text);
      case 'br': return ' ';
      case 'link': return plainInline((token as Tokens.Link).tokens);
      case 'image': return decoded((token as Tokens.Image).text);
      case 'text': return (token as Tokens.Text).tokens ? plainInline((token as Tokens.Text).tokens) : decoded((token as Tokens.Text).text);
      case 'escape': return (token as Tokens.Escape).text;
      default: return 'raw' in token ? token.raw : '';
    }
  }).join('');
}

function plainBlocks(tokens: Token[]): string[] {
  return tokens.flatMap((token): string[] => {
    switch (token.type) {
      case 'space': case 'hr': return [];
      case 'paragraph': case 'heading': case 'text': return [plainInline((token as Tokens.Paragraph).tokens ?? [token])];
      case 'list': return (token as Tokens.List).items.flatMap((item) => plainBlocks(item.tokens));
      case 'code': return [(token as Tokens.Code).text];
      case 'blockquote': return plainBlocks((token as Tokens.Blockquote).tokens);
      default: return ['raw' in token ? token.raw.trim() : ''];
    }
  });
}

/** An answer as the voice says it and the captions show it: its words, without the marks (baxy_mind speech_text.unmarked). */
export function plainOf(text: string): string {
  return plainBlocks(lexer(text)).join(' ').replace(/\s+/g, ' ').trim();
}
