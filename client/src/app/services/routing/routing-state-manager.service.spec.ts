import { TestBed } from '@angular/core/testing';

import { RoutingStateManagerService } from './routing-state-manager.service';

describe('RoutingStateManagerService', () => {
  let service: RoutingStateManagerService;

  beforeEach(() => {
    TestBed.configureTestingModule({});
    service = TestBed.inject(RoutingStateManagerService);
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });
});
