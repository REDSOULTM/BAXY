import type { Token, Tokens } from 'marked';
import { decoded, lexer } from './marks';
import type { ReactNode } from 'react';

/* The marks the model writes in an answer, drawn as what they mean (ABIERTOS_VIVO H1, VIVO2 F16, 2026-11-09: «**» showed as
   they were and its lists ran together). Rendering, not rewriting: every character the model wrote is either drawn as the
   mark it is or shown as text. CommonMark 0.31.2 (https://spec.commonmark.org/0.31.2/) read by marked's lexer
   (https://marked.js.org, MIT; GFM on, for «~~» and lists as the model writes them); its tokens become React elements here,
   never HTML: the view keeps no innerHTML. Emphasis, strong, code, lists, headings, quotes and rules are drawn. What the model
   writes as HTML is shown as its text and never runs; a link or an image it writes is shown as its words and its address,
   neither opened nor fetched (a picture would be a request to a server the model named). */

/** where a link or a picture pointed, beside its words, when the words do not already say it */
function address(words: string, href: string): string {
  return href && href !== words && href !== 'http://' + words && href !== 'mailto:' + words ? ` (${href})` : '';
}

function inline(tokens: Token[] | undefined, key: string): ReactNode[] {
  return (tokens ?? []).map((token, i) => {
    const k = key + '.' + i;
    switch (token.type) {
      case 'strong': return <strong key={k}>{inline((token as Tokens.Strong).tokens, k)}</strong>;
      case 'em': return <em key={k}>{inline((token as Tokens.Em).tokens, k)}</em>;
      case 'del': return <del key={k}>{inline((token as Tokens.Del).tokens, k)}</del>;
      case 'codespan': return <code key={k}>{decoded((token as Tokens.Codespan).text)}</code>;
      case 'br': return <br key={k} />;
      case 'link': {
        const link = token as Tokens.Link;
        return <span key={k}>{inline(link.tokens, k)}{address(link.text, link.href)}</span>;
      }
      case 'image': {
        const image = token as Tokens.Image;
        return <span key={k}>{decoded(image.text)}{address(image.text, image.href)}</span>;
      }
      case 'text': {
        const text = token as Tokens.Text;
        return text.tokens ? <span key={k}>{inline(text.tokens, k)}</span> : decoded(text.text);
      }
      case 'escape': return (token as Tokens.Escape).text;
      // inline HTML («<b>», «<script>…»), and anything else: the characters the model wrote
      default: return 'raw' in token ? token.raw : '';
    }
  });
}

function blocks(tokens: Token[], key: string): ReactNode[] {
  return tokens.map((token, i) => {
    const k = key + '.' + i;
    switch (token.type) {
      case 'space': return null;
      case 'paragraph': return <p key={k}>{inline((token as Tokens.Paragraph).tokens, k)}</p>;
      // a heading in an answer is a line of its own, strong: the conversation's sizes stay the design's
      case 'heading': return <p key={k} className="md-h" role="heading" aria-level={Math.min(6, 2 + (token as Tokens.Heading).depth)}><strong>{inline((token as Tokens.Heading).tokens, k)}</strong></p>;
      case 'list': {
        const list = token as Tokens.List;
        const items = list.items.map((item, j) => <li key={k + '.' + j}>{blocks(item.tokens, k + '.' + j)}</li>);
        return list.ordered
          ? <ol key={k} start={typeof list.start === 'number' && list.start !== 1 ? list.start : undefined}>{items}</ol>
          : <ul key={k}>{items}</ul>;
      }
      // a list item's text: its inline marks, with no paragraph of its own (a tight list, CommonMark 5.3)
      case 'text': {
        const text = token as Tokens.Text;
        return <span key={k}>{text.tokens ? inline(text.tokens, k) : decoded(text.text)}</span>;
      }
      case 'code': return <pre key={k}><code>{(token as Tokens.Code).text}</code></pre>;
      case 'blockquote': return <blockquote key={k}>{blocks((token as Tokens.Blockquote).tokens, k)}</blockquote>;
      case 'hr': return <hr key={k} />;
      // HTML blocks, tables, link definitions and anything else: as written
      default: return <p key={k}>{'raw' in token ? token.raw.trim() : ''}</p>;
    }
  });
}

/** An answer of the model's, its marks drawn (the reply's .tx). */
export function Marked({ text }: { text: string }) {
  return <>{blocks(lexer(text), 'm')}</>;
}
