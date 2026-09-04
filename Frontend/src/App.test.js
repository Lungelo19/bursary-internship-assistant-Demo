import { render, screen } from '@testing-library/react';
import App from './App';

test('renders the landing page headline', () => {
  render(<App />);
  const heading = screen.getByText(/find the right bursary/i);
  expect(heading).toBeInTheDocument();
});
