import { Injectable } from '@angular/core';
import { MatDialog } from '@angular/material/dialog';
import { MatSnackBar } from '@angular/material/snack-bar';
import { TranslocoService } from '@ngneat/transloco';
import { Observable } from 'rxjs';
import { ErrorDialogModel } from 'src/app/components/error-modal/error-dialog.model';
import { ErrorModalComponent } from 'src/app/components/error-modal/error-modal.component';

@Injectable({
  providedIn: 'root'
})
export class ErrorService {

  constructor(
    private readonly translocoService: TranslocoService,
    private readonly matSnackBar: MatSnackBar,
    private readonly matDialog: MatDialog,
  ) {}

  public displayErrorDialog(body: string, title = 'error.errorDialogTitle', buttonAcceptText = 'error.errorDialogOK', buttonCancelText?: string): Observable<void> {
    const data: ErrorDialogModel = {
      title,
      body,
      buttonAcceptText,
      buttonCancelText,
    }
    const dialogRef = this.matDialog.open(ErrorModalComponent, {
      data,
      disableClose: true,
      maxWidth: 600,
    })
    return dialogRef.afterClosed()
  }

  // Handle unknonw errors by simply displaying a generic error message and a console output
  // This should only be called as a last resort when the returned error does not match any of
  // to expected errors.
  public displayUnknownError(error: unknown) {
    console.error("unknown error occurred", error)
    this.showSnackBar("errro.genericError")
  }

  public displayConnectionError() {
    this.showSnackBar("error.genericApiError")
  }

  private showSnackBar(translationKey: string) {
    const errorText = this.translocoService.translate(translationKey)
    this.matSnackBar.open(errorText, undefined, { })
  }
}