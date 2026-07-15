type ThreadRenameKeyEvent = {
  isComposing: boolean;
  key: string;
  keyCode: number;
};

export function shouldCommitThreadRename(event: ThreadRenameKeyEvent) {
  return (
    event.key === "Enter" && !event.isComposing && event.keyCode !== 229
  );
}
