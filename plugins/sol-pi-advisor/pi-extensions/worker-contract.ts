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

function isScratch(candidate: string): boolean {
	const configured = process.env.SOL_PI_SCRATCH_DIR;
	if (!configured) return false;
	const absolute = path.resolve(process.cwd(), candidate.replace(/^@/, ""));
	const relative = path.relative(path.resolve(configured), absolute);
	return Boolean(relative) && !relative.startsWith(`..${path.sep}`) && !path.isAbsolute(relative);
}

function primaryOwnedCommandReason(command: string): string | undefined {
	const dependencyResolver =
		/\b(?:bunx|npx|npm\s+exec|pnpm\s+(?:dlx|exec)|yarn\s+(?:dlx|exec)|uvx|pipx\s+run)\b/i;
	if (dependencyResolver.test(command)) {
		return "Dependency-resolving commands are primary-owned. Do not work around this block; report the check as a handoff gap.";
	}

	const dependencyMutation =
		/\b(?:(?:bun|npm|pnpm|yarn)\s+(?:add|ci|install|remove|uninstall|update|upgrade)|(?:pip|pip3)\s+install|uv\s+(?:add|lock|sync)|poetry\s+(?:add|install|lock)|cargo\s+(?:add|update)|go\s+(?:get|mod\s+tidy))\b/i;
	if (dependencyMutation.test(command)) {
		return "Dependency installation or dependency-state mutation is primary-owned. Report the missing environment instead of changing it.";
	}

	const repositoryWideDeadCode = /\b(?:bun\s+(?:run\s+)?dead-code|knip)\b/i;
	if (repositoryWideDeadCode.test(command)) {
		return "Repository-wide dead-code checks are primary-owned because they may resolve dependencies. Report this check for primary verification.";
	}

	return undefined;
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
		if (
			(event.toolName === "write" || event.toolName === "edit") &&
			!isAllowed(String(event.input.path), allowed) &&
			!isScratch(String(event.input.path))
		) {
			return {
				block: true,
				reason: `Write is outside Sol-owned paths and the run scratch directory: ${String(event.input.path)}`,
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
			const primaryOwnedReason = primaryOwnedCommandReason(command);
			if (primaryOwnedReason) return { block: true, reason: primaryOwnedReason };
		}

		return undefined;
	});
}
