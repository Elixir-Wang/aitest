import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const inputSource = readFileSync(new URL("../src/components/ui/knowledge-chat-input.tsx", import.meta.url), "utf8");
const pageSource = readFileSync(new URL("../src/app/(main)/knowledge/page.tsx", import.meta.url), "utf8");
const apiClientSource = readFileSync(new URL("../src/lib/api-client.ts", import.meta.url), "utf8");

function sourceAfter(marker) {
  const markerIndex = pageSource.indexOf(marker);
  assert.notEqual(markerIndex, -1, `missing marker: ${marker}`);
  return pageSource.slice(markerIndex);
}

function sourceBetween(startMarker, endMarker) {
  const startIndex = pageSource.indexOf(startMarker);
  assert.notEqual(startIndex, -1, `missing start marker: ${startMarker}`);
  const endIndex = pageSource.indexOf(endMarker, startIndex);
  assert.notEqual(endIndex, -1, `missing end marker: ${endMarker}`);
  return pageSource.slice(startIndex, endIndex);
}

test("knowledge chat input exposes model switch instead of source mode switch", () => {
  assert.doesNotMatch(inputSource, /sourceModes/);
  assert.doesNotMatch(inputSource, /onSourceChange/);
  assert.doesNotMatch(inputSource, /需求 \+ 探索/);
  assert.match(inputSource, /modelProviders/);
  assert.match(inputSource, /selectedModelProviderId/);
  assert.match(inputSource, /onModelProviderChange/);
});

test("project knowledge page keeps requirements and explorations as default query sources", () => {
  assert.match(pageSource, /include_requirements: true/);
  assert.match(pageSource, /include_explorations: true/);
  assert.doesNotMatch(pageSource, /projectBuildForm\.includeRequirements/);
  assert.doesNotMatch(pageSource, /projectBuildForm\.includeExplorations/);
});

test("project knowledge model switch reads and writes the knowledge query assignment", () => {
  assert.match(pageSource, /KNOWLEDGE_QUERY_CAPABILITY_ID = "knowledge_query"/);
  assert.match(pageSource, /apiRequest<ApiModelAssignment\[]>\("\/model-assignments"\)/);
  assert.match(pageSource, /apiRequest<ApiModelProvider\[]>\("\/models\/providers"\)/);
  assert.match(pageSource, /`\/model-assignments\/\$\{KNOWLEDGE_QUERY_CAPABILITY_ID\}`/);
});

test("project knowledge chat history is collapsed behind the top controls by default", () => {
  assert.match(pageSource, /const \[historyOpen, setHistoryOpen\] = useState\(false\)/);
  assert.match(pageSource, /function KnowledgeChatTopControls/);
  assert.match(pageSource, /aria-label="展开对话历史"/);
  assert.match(pageSource, /aria-label="新建对话"/);
  assert.doesNotMatch(pageSource, /lg:grid-cols-\[3\.5rem_minmax\(0,1fr\)\]/);
});

test("project knowledge chat history controls open for selected knowledge scope and gate history actions to project conversations", () => {
  assert.match(
    pageSource,
    /projectConversationEnabled=\{effectiveKnowledgeScope === "project" && Boolean\(projectId\)\}/,
  );
  assert.match(pageSource, /projectSelected=\{effectiveKnowledgeScope === "all" \|\| Boolean\(projectId\)\}/);
  assert.match(pageSource, /projectConversationEnabled: boolean/);
  assert.match(pageSource, /projectSelected: boolean/);
  const projectHistoryPanelSource = sourceAfter("function ProjectKnowledgeWorkspace");
  assert.match(projectHistoryPanelSource, /if \(!projectSelected\)/);
  assert.match(projectHistoryPanelSource, /setHistoryOpen\(false\)/);
  assert.match(projectHistoryPanelSource, /\[projectSelected\]/);
  assert.match(pageSource, /const projectHistoryOpen = historyOpen/);
  assert.match(pageSource, /if \(!projectSelected \|\| running\)/);
  assert.match(pageSource, /setHistoryOpen\(true\)/);
  assert.match(pageSource, /全部项目知识库暂不保存历史对话/);
  assert.match(pageSource, /\{projectHistoryOpen \? \(\s+<aside/);
  assert.match(
    pageSource,
    /aria-label="展开对话历史"[\s\S]*?disabled=\{!projectSelected \|\| running\}[\s\S]*?onClick=\{onHistoryOpen\}/,
  );
  assert.match(projectHistoryPanelSource, /onClick=\{\(\) => onConversationOpen\(conversation\.id\)\}/);
  assert.match(projectHistoryPanelSource, /onClick=\{\(\) => onConversationDelete\(conversation\.id\)\}/);
  assert.match(projectHistoryPanelSource, /disabled=\{!projectConversationEnabled \|\| running\}/);
});

test("knowledge API types support all-project query metadata", () => {
  assert.match(apiClientSource, /project_id: string \| null/);
  assert.match(apiClientSource, /project_name: string \| null/);
  assert.match(apiClientSource, /conversation: ApiKnowledgeConversation \| null/);
});

test("knowledge page derives chat scope from global project context and local selection", () => {
  assert.match(pageSource, /scope: globalProjectScope/);
  assert.match(pageSource, /const \[knowledgeScope, setKnowledgeScope\] = useState<"all" \| "project">\("all"\)/);
  assert.match(pageSource, /const \[knowledgeProjectId, setKnowledgeProjectId\] = useState<string \| null>\(null\)/);
  assert.match(
    pageSource,
    /const activeCurrentProject = activeProjects\.find\(\(project\) => project\.id === currentProjectId\) \?\? null/,
  );
  assert.match(pageSource, /const effectiveKnowledgeScope =/);
  assert.match(pageSource, /const effectiveProjectId =/);
  assert.match(
    pageSource,
    /const selectedProjectScope = effectiveKnowledgeScope === "project" \? \(effectiveProjectId \?\? ""\) : "all"/,
  );
  assert.doesNotMatch(pageSource, /currentProjectId \?\? activeProjects\[0\]\?\.id \?\? null/);
  assert.doesNotMatch(pageSource, /activeProjects\[0\]/);
  assert.doesNotMatch(pageSource, /activeProjects\.at\(0\)/);
});

test("knowledge page preserves local project selection while globally locked to a project", () => {
  assert.match(
    pageSource,
    /const effectiveKnowledgeScope = globalProjectScope === "project" && activeCurrentProject \? "project" : knowledgeScope/,
  );
  assert.match(pageSource, /globalProjectScope === "project"\s+\? \(activeCurrentProject\?\.id \?\? null\)/);
  const projectLockEffectSource = sourceBetween(
    'if (globalProjectScope === "project")',
    "const activeProjectIds = new Set",
  );
  assert.match(projectLockEffectSource, /return/);
  assert.doesNotMatch(projectLockEffectSource, /setKnowledgeScope\("project"\)/);
  assert.doesNotMatch(projectLockEffectSource, /setKnowledgeProjectId\(activeCurrentProject\?\.id/);
  assert.doesNotMatch(projectLockEffectSource, /setKnowledgeProjectId\(currentProjectId/);
});

test("knowledge page clears invalid local project selection only under global all validation", () => {
  assert.match(
    pageSource,
    /const activeProjectIdsKey = activeProjects\.map\(\(project\) => project\.id\)\.join\("\|"\)/,
  );
  assert.match(
    pageSource,
    /const activeProjectIds = new Set\(activeProjectIdsKey \? activeProjectIdsKey\.split\("\|"\) : \[\]\)/,
  );
  assert.match(
    pageSource,
    /if \(knowledgeScope === "project" && knowledgeProjectId && !activeProjectIds\.has\(knowledgeProjectId\)\)/,
  );
  assert.match(pageSource, /setKnowledgeScope\("all"\)/);
  assert.match(pageSource, /setKnowledgeProjectId\(null\)/);
  assert.match(pageSource, /\[activeProjectIdsKey, globalProjectScope, knowledgeProjectId, knowledgeScope\]/);
});

test("knowledge page routes stream requests by effective scope", () => {
  assert.match(pageSource, /effectiveKnowledgeScope === "project" && !effectiveProjectId/);
  assert.match(
    pageSource,
    /submittedKnowledgeScope === "all"\s+\? "\/knowledge\/query\/stream"\s+: `\/projects\/\$\{submittedProjectId\}\/knowledge\/query\/stream`/,
  );
  assert.match(pageSource, /fetch\(`\$\{API_BASE_URL\}\$\{streamPath\}`/);
});

test("knowledge page only uses conversation endpoints for specific project scope", () => {
  assert.match(
    pageSource,
    /if \(isCompanyKnowledge \|\| effectiveKnowledgeScope !== "project" \|\| !effectiveProjectId\)/,
  );
  assert.match(pageSource, /if \(effectiveKnowledgeScope !== "project" \|\| !projectId\)/);
  assert.match(pageSource, /const conversation = event\.result\.conversation/);
  assert.match(
    pageSource,
    /if \(isCurrentProjectQueryScope\(\) && submittedKnowledgeScope === "project" && conversation\)/,
  );
});

test("knowledge page guards stale stream metadata writes after scope changes", () => {
  assert.match(pageSource, /const projectQueryRunIdRef = useRef\(0\)/);
  assert.match(pageSource, /const latestProjectQueryScopeRef = useRef\(""\)/);
  assert.match(
    pageSource,
    /const submittedQueryScopeKey = `\$\{submittedKnowledgeScope\}:\$\{submittedProjectId \?\? ""\}`/,
  );
  assert.match(pageSource, /const isCurrentProjectQueryScope = \(\) =>/);
  assert.match(pageSource, /projectQueryRunIdRef\.current === queryRunId/);
  assert.match(pageSource, /latestProjectQueryScopeRef\.current === submittedQueryScopeKey/);
  assert.match(pageSource, /const conversation = event\.result\.conversation/);
  assert.match(
    pageSource,
    /if \(isCurrentProjectQueryScope\(\) && submittedKnowledgeScope === "project" && conversation\)/,
  );
  assert.match(pageSource, /setActiveProjectConversationId\(conversation\.id\)/);
  assert.match(pageSource, /setProjectConversations\(\(items\) => upsertConversation\(items, conversation\)\)/);
  assert.match(pageSource, /if \(isCurrentProjectQueryScope\(\)\) \{/);
  assert.match(pageSource, /mergeAssistantStreamResult\(message, event\.result\)/);
});

test("knowledge page guards stale stream deltas and lifecycle writes", () => {
  const streamSource = sourceAfter("async function queryProjectKnowledge");
  assert.match(streamSource, /if \(event\.type === "message_delta"\)/);
  assert.match(streamSource, /if \(isCurrentProjectQueryScope\(\)\) \{[\s\S]*?message\.id === assistantMessageId/);
  assert.match(streamSource, /catch \(nextError\) \{\s+if \(isCurrentProjectQueryScope\(\)\) \{/);
  assert.match(streamSource, /setError\(nextError instanceof Error \? nextError\.message : "查询项目知识库失败。"\)/);
  assert.match(
    streamSource,
    /setProjectMessages\(\(messages\) => messages\.filter\(\(message\) => message\.id !== assistantMessageId\)\)/,
  );
  assert.match(streamSource, /finally \{\s+if \(isCurrentProjectQueryScope\(\)\) \{\s+setRunning\(false\)/);
});

test("knowledge page resets async lifecycle state when project scope changes", () => {
  const resetSource = sourceBetween("void projectResetKey;", "const loadProjectConversations = useCallback");
  assert.match(resetSource, /projectQueryRunIdRef\.current \+= 1/);
  assert.match(resetSource, /projectConversationLoadRunIdRef\.current \+= 1/);
  assert.match(resetSource, /projectConversationOpenRunIdRef\.current \+= 1/);
  assert.match(resetSource, /latestProjectQueryScopeRef\.current = projectResetKey/);
  assert.match(resetSource, /setError\(""\)/);
  assert.match(resetSource, /setLoading\(false\)/);
  assert.match(resetSource, /setRunning\(false\)/);
});

test("knowledge page guards stale project conversation list loads", () => {
  const conversationLoadSource = sourceBetween(
    "const loadProjectConversations = useCallback",
    "const openProjectConversation = useCallback",
  );
  assert.match(pageSource, /const projectConversationLoadRunIdRef = useRef\(0\)/);
  assert.match(conversationLoadSource, /const conversationLoadRunId = projectConversationLoadRunIdRef\.current \+ 1/);
  assert.match(conversationLoadSource, /projectConversationLoadRunIdRef\.current = conversationLoadRunId/);
  assert.match(conversationLoadSource, /const isCurrentConversationLoad = \(\) =>/);
  assert.match(conversationLoadSource, /projectConversationLoadRunIdRef\.current === conversationLoadRunId/);
  assert.match(conversationLoadSource, /latestProjectQueryScopeRef\.current === `project:\$\{targetProjectId\}`/);
  assert.match(
    conversationLoadSource,
    /if \(isCurrentConversationLoad\(\)\) \{\s+setProjectConversations\(conversations\)/,
  );
  assert.match(conversationLoadSource, /catch \(nextError\) \{\s+if \(isCurrentConversationLoad\(\)\) \{/);
  assert.match(conversationLoadSource, /finally \{\s+if \(isCurrentConversationLoad\(\)\) \{\s+setLoading\(false\)/);
});

test("knowledge page guards stale project conversation opens", () => {
  const conversationOpenSource = sourceBetween(
    "const openProjectConversation = useCallback",
    "void loadProjectConversations(effectiveProjectId);",
  );
  assert.match(pageSource, /const projectConversationOpenRunIdRef = useRef\(0\)/);
  assert.match(conversationOpenSource, /const conversationOpenRunId = projectConversationOpenRunIdRef\.current \+ 1/);
  assert.match(conversationOpenSource, /projectConversationOpenRunIdRef\.current = conversationOpenRunId/);
  assert.match(conversationOpenSource, /const isCurrentConversationOpen = \(\) =>/);
  assert.match(conversationOpenSource, /projectConversationOpenRunIdRef\.current === conversationOpenRunId/);
  assert.match(conversationOpenSource, /latestProjectQueryScopeRef\.current === `project:\$\{targetProjectId\}`/);
  assert.match(
    conversationOpenSource,
    /if \(isCurrentConversationOpen\(\)\) \{[\s\S]*?setActiveProjectConversationId\(detail\.conversation\.id\)/,
  );
  assert.match(conversationOpenSource, /setProjectMessages\(detail\.messages\.map\(projectMessageFromApi\)\)/);
  assert.match(conversationOpenSource, /setProjectChatDraft\(""\)/);
  assert.match(conversationOpenSource, /catch \(nextError\) \{\s+if \(isCurrentConversationOpen\(\)\) \{/);
  assert.match(conversationOpenSource, /finally \{\s+if \(isCurrentConversationOpen\(\)\) \{\s+setLoading\(false\)/);
});

test("knowledge source refs display project attribution when present", () => {
  const sourceRefRenderSource = sourceAfter("来源引用");
  assert.match(sourceRefRenderSource, /ref\.project_name/);
  assert.match(sourceRefRenderSource, /<Badge variant="secondary">\{ref\.project_name\}<\/Badge>/);
});

test("knowledge chat input consumes project scope selector props", () => {
  assert.match(inputSource, /projectScopeOptions/);
  assert.match(inputSource, /selectedProjectScope/);
  assert.match(inputSource, /onProjectScopeChange/);
  assert.match(inputSource, /aria-label="选择知识检索项目"/);
  assert.doesNotMatch(pageSource, /void onProjectScopeChange/);
  assert.doesNotMatch(pageSource, /void projectScopeOptions/);
  assert.doesNotMatch(pageSource, /void selectedProjectScope/);
  assert.doesNotMatch(inputSource, /void onProjectScopeChange/);
  assert.doesNotMatch(inputSource, /void projectScopeOptions/);
  assert.doesNotMatch(inputSource, /void selectedProjectScope/);
});

test("knowledge chat input keeps removed fake/deep-thinking/context controls out", () => {
  assert.doesNotMatch(inputSource, /Clock/);
  assert.doesNotMatch(inputSource, /thinkingEnabled/);
  assert.doesNotMatch(inputSource, /aria-label="深度思考"/);
  assert.doesNotMatch(inputSource, /添加上下文/);
  assert.doesNotMatch(inputSource, /\bPlus\b/);
});

test("knowledge chat collapsed model label hides provider while dropdown still shows it", () => {
  assert.match(inputSource, /const modelLabel = selectedModelProvider\s+\? selectedModelProvider\.model/);
  assert.doesNotMatch(inputSource, /\$\{provider\.provider\}\s*\/\s*\$\{provider\.model\}/);
  assert.doesNotMatch(inputSource, /\$\{selectedModelProvider\.provider\}\s*\/\s*\$\{selectedModelProvider\.model\}/);
  assert.match(inputSource, /\{provider\.model\}/);
  assert.match(inputSource, /\{provider\.provider\}/);
  assert.match(inputSource, /items-baseline gap-2/);
  assert.match(inputSource, /align="center"/);
  assert.match(inputSource, /compact \? "text-xs" : "text-sm"/);
  assert.doesNotMatch(inputSource, /className="w-64/);
  assert.doesNotMatch(inputSource, /align="end"/);
  assert.doesNotMatch(inputSource, /align="start"/);
  assert.doesNotMatch(inputSource, /flex-col items-start/);
});
