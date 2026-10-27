import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from '../components/layout/AppLayout';
import { DashboardOverview } from '../features/dashboard/DashboardOverview';
import { JobsList } from '../features/jobs/JobsList';
import { CandidateProfileView } from '../features/profile/CandidateProfileView';
import { ResumeWorkspace } from '../features/resumes/ResumeWorkspace';
import { ApplicationQueue } from '../features/applications/ApplicationQueue';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <AppLayout />,
    children: [
      {
        index: true,
        element: <DashboardOverview />,
      },
      {
        path: 'jobs',
        element: <JobsList />,
      },
      {
        path: 'profile',
        element: <CandidateProfileView />,
      },
      {
        path: 'resumes',
        element: <ResumeWorkspace />,
      },
      {
        path: 'applications',
        element: <ApplicationQueue />,
      },
      {
        path: '*',
        element: <Navigate to="/" replace />,
      },
    ],
  },
]);
