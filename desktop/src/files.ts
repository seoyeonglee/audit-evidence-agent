import { constants } from "node:fs";
import { open, lstat, writeFile } from "node:fs/promises";
import { basename, extname } from "node:path";
import type { SelectedEvidence } from "./contracts.js";
async function readEvidence(path: string): Promise<SelectedEvidence> {
  const extension = extname(path).toLowerCase();
  const media: Record<string, string> = {
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".json": "application/json",
  };
  if (!media[extension]) throw new Error("Select text, CSV or JSON evidence");
  const before = await lstat(path);
  if (!before.isFile() || before.isSymbolicLink())
    throw new Error("Regular files only");
  const handle = await open(
    path,
    constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0),
  );
  try {
    const stat = await handle.stat();
    if (
      !stat.isFile() ||
      stat.ino !== before.ino ||
      stat.dev !== before.dev ||
      stat.size > 1048576
    )
      throw new Error("File is unsafe or exceeds 1 MiB");
    const bytes = await handle.readFile();
    if (bytes.length > 1048576) throw new Error("File exceeds 1 MiB");
    const content = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    if (
      !content.trim() ||
      [...content].length > 200000 ||
      content.includes("\0")
    )
      throw new Error("Invalid or oversized evidence text");
    const filename = basename(path);
    if ([...filename].length > 120)
      throw new Error("Filename exceeds 120 characters");
    return {
      cancelled: false,
      filename,
      media_type: media[extension],
      content,
    };
  } finally {
    await handle.close();
  }
}

export async function readSelectedEvidence(
  path: string,
): Promise<SelectedEvidence> {
  try {
    return await readEvidence(path);
  } catch {
    throw new Error(
      "Evidence could not be read. Choose a regular UTF-8 text, CSV or JSON file within the limits.",
    );
  }
}
export async function writeSelectedReport(
  path: string,
  content: string,
): Promise<void> {
  try {
    await writeFile(path, content, { encoding: "utf8", flag: "w" });
  } catch {
    throw new Error("Report could not be saved. Choose a writable file.");
  }
}
