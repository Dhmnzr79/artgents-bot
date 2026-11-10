const normalize = value => String(value ?? '').toLocaleLowerCase('ru').replace(/ё/g, 'е').trim();
const words = value => value.match(/[\p{L}\p{N}]+/gu) || [];

// One insertion, deletion, substitution, or adjacent transposition; whole words only.
function oneTypo(a, b) {
  if (Math.abs(a.length - b.length) > 1) return false;
  let i = 0;
  while (i < a.length && i < b.length && a[i] === b[i]) i++;
  if (i === Math.min(a.length, b.length)) return true;
  if (a.length < b.length) return a.slice(i) === b.slice(i + 1);
  if (a.length > b.length) return a.slice(i + 1) === b.slice(i);
  return a.slice(i + 1) === b.slice(i + 1) ||
    (a[i] === b[i + 1] && a[i + 1] === b[i] && a.slice(i + 2) === b.slice(i + 2));
}

export function matchesCatalogSearch(fields, query) {
  const text = normalize(fields.filter(Boolean).join(' '));
  const needle = normalize(query);
  if (text.includes(needle)) return true;
  const terms = words(needle), candidates = words(text);
  if (!terms.length) return false;
  return terms.every(term => candidates.some(candidate =>
    // Numeric identifiers are exact, including when another word has a typo.
    (/\p{N}/u.test(term) ? candidate === term : candidate.includes(term)) ||
    (term.length >= 4 && candidate.length >= 4 &&
      !/\p{N}/u.test(term + candidate) && oneTypo(term, candidate))));
}
