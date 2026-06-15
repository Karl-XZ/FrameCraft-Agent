import React, { useEffect } from 'react';
import StudioLayout from '../components/layout/StudioLayout';
import { useProjectStore } from '../store/projectStore';

export default function StudioPage() {
  const { setStep } = useProjectStore();

  // Read step from URL query param
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const step = params.get('step');
    if (step && ['upload', 'analyze', 'plan', 'generate', 'result'].includes(step)) {
      setStep(step as any);
    }
  }, []);

  return <StudioLayout />;
}
