import { NgModule } from '@angular/core';
import { TranslocoModule } from '@ngneat/transloco';
import { MaterialModule } from './material/material.module';
import { SafePipe } from './pipes/safe.pipe';
import { ResponsiveDirective } from './directives/responsive.directive';
import { ReactiveFormsModule } from '@angular/forms';
import { ToAbsolutePipe } from './pipes/to-absolute.pipe';

@NgModule({
  declarations: [
    SafePipe,
    ResponsiveDirective,
    ToAbsolutePipe,
  ],
  imports: [
    MaterialModule,
    TranslocoModule,
    ReactiveFormsModule,
  ],
  exports: [
    SafePipe,
    MaterialModule,
    TranslocoModule,
    ResponsiveDirective,
    ReactiveFormsModule,
    ToAbsolutePipe,
  ]
})
export class AppCommonModule { }
