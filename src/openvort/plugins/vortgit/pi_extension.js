// OpenVort <-> Pi custom-provider bridge.
//
// Pi (https://pi.dev) has no built-in slot for OpenVort's dynamic model library, so we
// register a single OpenAI-compatible provider named "openvort" whose endpoint, model and
// API key are supplied at runtime through environment variables injected by CLIRunner
// (see cli_runner._inject_pi_env). Keeping the key in the environment — never in this file —
// avoids writing credentials to disk.
//
// Loaded explicitly via `pi --extension <this file>`; selected via `--model openvort/<id>`.
export default function (pi) {
  const baseUrl = process.env.OPENVORT_PI_BASE_URL;
  const model = process.env.OPENVORT_PI_MODEL;
  const apiKey = process.env.OPENVORT_PI_API_KEY;
  if (!baseUrl || !model || !apiKey) {
    return;
  }
  pi.registerProvider("openvort", {
    baseUrl,
    apiKey,
    api: "openai-completions",
    models: [
      {
        id: model,
        name: model,
        reasoning: false,
        input: ["text"],
        cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
        contextWindow: 128000,
        maxTokens: 4096,
      },
    ],
  });
}
