import React, { useEffect } from 'react';
import StudioLayout from '../components/layout/StudioLayout';
import { useProjectStore } from '../store/projectStore';
import { useStudioWorkflow } from '../hooks/useStudioWorkflow';

export default function StudioPage() {
  const { setStep } = useProjectStore();
  const { loadProject } = useStudioWorkflow();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const projectId = params.get('project');
    if (projectId) {
      void loadProject(projectId);
      return;
    }
    const step = params.get('step');
    if (step && ['upload', 'analyze', 'plan', 'generate', 'result'].includes(step)) {
      setStep(step as any);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <StudioLayout />;
}
