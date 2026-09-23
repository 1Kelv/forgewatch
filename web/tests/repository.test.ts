import assert from "node:assert/strict";
import test from "node:test";

import { nextScanAt, parseGitHubRepository, validateBranch } from "../lib/repository";
import { isGitHubLoginAllowed } from "../lib/env";

test("accepts a GitHub URL and returns owner/repository", () => {
  assert.equal(parseGitHubRepository("https://github.com/acme/widget.git"), "acme/widget");
  assert.equal(parseGitHubRepository("https://github.com/acme/widget.git/"), "acme/widget");
  assert.equal(parseGitHubRepository("1Kelv/forgewatch"), "1Kelv/forgewatch");
});

test("rejects non-GitHub and malformed repository URLs", () => {
  assert.throws(() => parseGitHubRepository("https://example.com/owner/repository"));
  assert.throws(() => parseGitHubRepository("https://github.com/owner/repository/issues"));
  assert.throws(() => parseGitHubRepository("owner"));
});

test("validates branches without accepting revision traversal", () => {
  assert.equal(validateBranch("feature/report-ui"), "feature/report-ui");
  assert.throws(() => validateBranch("feature/../main"));
  assert.throws(() => validateBranch("main; touch file"));
});

test("calculates daily and weekly schedules", () => {
  const from = new Date("2026-09-23T10:00:00Z");
  assert.equal(nextScanAt("manual", from), null);
  assert.equal(nextScanAt("daily", from)?.toISOString(), "2026-09-24T03:17:00.000Z");
  assert.equal(nextScanAt("weekly", from)?.toISOString(), "2026-09-30T03:17:00.000Z");
});

test("allows named GitHub users and supports an explicit public-access wildcard", () => {
  const previous = process.env.FORGEWATCH_ALLOWED_GITHUB_LOGINS;
  try {
    process.env.FORGEWATCH_ALLOWED_GITHUB_LOGINS = "1Kelv, invited-user";
    assert.equal(isGitHubLoginAllowed("1kelv"), true);
    assert.equal(isGitHubLoginAllowed("INVITED-USER"), true);
    assert.equal(isGitHubLoginAllowed("someone-else"), false);

    process.env.FORGEWATCH_ALLOWED_GITHUB_LOGINS = "*";
    assert.equal(isGitHubLoginAllowed("someone-else"), true);
  } finally {
    if (previous === undefined) delete process.env.FORGEWATCH_ALLOWED_GITHUB_LOGINS;
    else process.env.FORGEWATCH_ALLOWED_GITHUB_LOGINS = previous;
  }
});
