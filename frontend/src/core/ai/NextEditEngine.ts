export interface NextEditPrediction {
  id: string;
  targetFile: string;
  reason: string;
  confidence: number;
  snippetHint?: string;
}

export class NextEditEngine {
  private editHistory: Array<{ filepath: string; timestamp: number }> = [];
  private confidenceThreshold: number = 0.6;

  public recordEdit(filepath: string): void {
    const norm = filepath.replace(/\\/g, '/');
    this.editHistory.push({ filepath: norm, timestamp: Date.now() });
    if (this.editHistory.length > 50) {
      this.editHistory.shift();
    }
  }

  public predictNextEdits(currentFile: string, allWorkspaceFiles: string[]): NextEditPrediction[] {
    if (!currentFile || !allWorkspaceFiles || allWorkspaceFiles.length === 0) {
      return [];
    }

    const currentNorm = currentFile.replace(/\\/g, '/');
    const basename = currentNorm.split('/').pop() || '';
    const nameWithoutExt = basename.substring(0, basename.lastIndexOf('.')) || basename;
    const predictions: NextEditPrediction[] = [];

    allWorkspaceFiles.forEach((file) => {
      const fileNorm = file.replace(/\\/g, '/');
      if (fileNorm === currentNorm) return;

      const otherBasename = fileNorm.split('/').pop() || '';
      const otherNameNoExt = otherBasename.substring(0, otherBasename.lastIndexOf('.')) || otherBasename;

      // 1. Direct Test relationship (UserService.ts -> UserService.test.ts)
      if (otherNameNoExt === `${nameWithoutExt}.test` || otherNameNoExt === `${nameWithoutExt}.spec` || fileNorm.includes(`__tests__/${nameWithoutExt}`)) {
        predictions.push({
          id: `test-${fileNorm}`,
          targetFile: fileNorm,
          reason: `Associated test suite for ${basename}`,
          confidence: 0.95
        });
      }

      // 2. Type/Interface definition relationship (UserService.ts -> UserTypes.ts or types/User.ts)
      else if (fileNorm.includes('/types/') || fileNorm.includes('/schemas/') || otherNameNoExt.toLowerCase().includes(nameWithoutExt.toLowerCase())) {
        predictions.push({
          id: `type-${fileNorm}`,
          targetFile: fileNorm,
          reason: `Related domain schema/types for ${basename}`,
          confidence: 0.75
        });
      }

      // 3. Same directory companion
      else if (fileNorm.substring(0, fileNorm.lastIndexOf('/')) === currentNorm.substring(0, currentNorm.lastIndexOf('/'))) {
        predictions.push({
          id: `companion-${fileNorm}`,
          targetFile: fileNorm,
          reason: `Co-located file in same module directory`,
          confidence: 0.65
        });
      }
    });

    return predictions
      .filter((p) => p.confidence >= this.confidenceThreshold)
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, 5);
  }
}

export const nextEditEngine = new NextEditEngine();
