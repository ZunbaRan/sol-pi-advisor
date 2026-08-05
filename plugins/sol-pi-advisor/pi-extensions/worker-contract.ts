import path from "node:path";
import { defineTool, type ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

type Handoff = {
	status: "complete" | "partial" | "blocked";
	objective: string;
	changes: Array<{ file: string; summary: string }>;
	checks: Array<{ command: string; result: string }>;
	gaps: string[];
	judgmentCalls: string[];
};

function allowedPaths(): string[] {
	const raw = process.env.SOL_PI_ALLOWED_PATHS_JSON;
	if (!raw) return [];
	const parsed = JSON.parse(raw);
	return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === "string") : [];
}

function isAllowed(candidate: string, allowed: string[]): boolean {
	const cwd = process.cwd();
	const absolute = path.resolve(cwd, candidate.replace(/^@/, ""));
	const relative = path.relative(cwd, absolute).split(path.sep).join("/");
	if (!relative || relative.startsWith("../") || path.isAbsolute(relative)) return false;
	return allowed.some((prefix) => relative === prefix || relative.startsWith(`${prefix}/`));
}

const submitHandoff = defineTool({
	name: "submit_handoff",
	label: "Submit Sol Pi handoff",
	description: "Submit the final structured implementation handoff and end the current Pi turn.",
	promptSnippet: "Submit the final implementation handoff as the last action",
	promptGuidelines: [
		"Call submit_handoff exactly once as your final action after implementation and verification.",
		"Do not emit another assistant response after submit_handoff.",
	],
	parameters: Type.Object({
		status: Type.Union([Type.Literal("complete"), Type.Literal("partial"), Type.Literal("blocked")]),
		objective: Type.String(),
		changes: Type.Array(
			Type.Object({
				file: Type.String(),
				summary: Type.String(),
			}),
		),
		checks: Type.Array(
			Type.Object({
				command: Type.String(),
				result: Type.String(),
			}),
		),
		gaps: Type.Array(Type.String()),
		judgmentCalls: Type.Array(Type.String()),
	}),
	async execute(_toolCallId, params) {
		return {
			content: [{ type: "text" as const, text: `Submitted ${params.status} implementation handoff.` }],
			details: params satisfies Handoff,
			terminate: true,
		};
	},
});

export default function workerContract(pi: ExtensionAPI) {
	pi.registerTool(submitHandoff);

	pi.on("tool_call", (event) => {
		const allowed = allowedPaths();
		if ((event.toolName === "write" || event.toolName === "edit") && !isAllowed(String(event.input.path), allowed)) {
			return {
				block: true,
				reason: `Write is outside Sol-owned paths: ${String(event.input.path)}`,
			};
		}

		if (event.toolName === "bash") {
			const command = String(event.input.command);
			const forbidden =
				/\bgit\s+(?:-[^\s]+\s+)*(?:add|commit|push|fetch|pull|merge|rebase|cherry-pick|reset|clean|checkout|switch|branch|tag|stash|worktree)\b/i;
			const prOperation = /\b(?:gh|glab)\s+pr\b/i;
			if (forbidden.test(command) || prOperation.test(command)) {
				return { block: true, reason: "Git history, remote, worktree, and PR operations are owned by primary Sol." };
			}
		}

		return undefined;
	});
}
