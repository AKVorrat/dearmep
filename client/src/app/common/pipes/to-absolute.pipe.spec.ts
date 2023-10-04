import { BaseUrlService } from '../services/base-url.service';
import { ToAbsolutePipe } from './to-absolute.pipe';

describe('ToAbsolutePipe', () => {
  it('create an instance', () => {
    const pipe = new ToAbsolutePipe({} as BaseUrlService);
    expect(pipe).toBeTruthy();
  });
});
