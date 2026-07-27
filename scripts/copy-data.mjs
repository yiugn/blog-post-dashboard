import { copyFileSync, existsSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

const destination = resolve("dist", "data");
const files = ["posts.json", "posts.csv"];

mkdirSync(destination, { recursive: true });

for (const file of files) {
  const sourceFile = resolve("data", file);
  if (!existsSync(sourceFile)) {
    throw new Error(`Dashboard data file was not found: ${sourceFile}`);
  }
  copyFileSync(sourceFile, resolve(destination, file));
}

console.log(`Copied ${files.join(", ")} to ${destination}`);
