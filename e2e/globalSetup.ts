import { ensureAllFixtures } from './fixtures/imageFixtures';

export default async function globalSetup(): Promise<void> {
  ensureAllFixtures();
}
