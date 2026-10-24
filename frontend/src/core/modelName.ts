/**
 * Split a model id for display: who publishes it, its name, and its variant.
 * "google/gemma-4-26b-a4b-it" -> google / gemma-4-26b-a4b-it;
 * "gemma3:4b" -> gemma3 + 4b; "hf.co/user/Model-GGUF:Q4_K_M" -> hf.co/user / Model-GGUF + Q4_K_M.
 */
export function modelNameParts(id: string): { vendor: string; name: string; tag: string } {
  const trimmed = id.trim();
  const slash = trimmed.lastIndexOf('/');
  const vendor = slash > 0 ? trimmed.slice(0, slash) : '';
  const rest = slash > 0 ? trimmed.slice(slash + 1) : trimmed;
  const colon = rest.lastIndexOf(':');
  const tag = colon > 0 && colon < rest.length - 1 ? rest.slice(colon + 1) : '';
  return { vendor, name: tag ? rest.slice(0, colon) : rest || trimmed, tag };
}
