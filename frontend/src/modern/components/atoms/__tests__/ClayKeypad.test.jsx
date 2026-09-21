import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ClayKeypad from '../ClayKeypad';

describe('ClayKeypad Component', () => {
  it('renders all digits 0 through 9', () => {
    render(<ClayKeypad onKeyPress={vi.fn()} onDelete={vi.fn()} onClear={vi.fn()} />);

    for (let i = 0; i <= 9; i++) {
      expect(screen.getByRole('button', { name: String(i) })).toBeInTheDocument();
    }
  });

  it('renders clear (साफ़) and backspace buttons', () => {
    const { container } = render(
      <ClayKeypad onKeyPress={vi.fn()} onDelete={vi.fn()} onClear={vi.fn()} />
    );

    expect(screen.getByRole('button', { name: /साफ़/i })).toBeInTheDocument();
    // Backspace button contains Delete icon
    const backspaceBtn = container.querySelector('button .text-manjistha-red')?.closest('button');
    expect(backspaceBtn).toBeInTheDocument();
  });

  it('invokes onKeyPress with the correct digit when numeric buttons are clicked', async () => {
    const handleKeyPress = vi.fn();
    render(<ClayKeypad onKeyPress={handleKeyPress} onDelete={vi.fn()} onClear={vi.fn()} />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: '5' }));
    expect(handleKeyPress).toHaveBeenCalledWith('5');

    await user.click(screen.getByRole('button', { name: '9' }));
    expect(handleKeyPress).toHaveBeenCalledWith('9');

    await user.click(screen.getByRole('button', { name: '0' }));
    expect(handleKeyPress).toHaveBeenCalledWith('0');

    expect(handleKeyPress).toHaveBeenCalledTimes(3);
  });

  it('invokes onClear when clear button is clicked', async () => {
    const handleClear = vi.fn();
    render(<ClayKeypad onKeyPress={vi.fn()} onDelete={vi.fn()} onClear={handleClear} />);

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /साफ़/i }));
    expect(handleClear).toHaveBeenCalledTimes(1);
  });

  it('invokes onDelete when backspace button is clicked', async () => {
    const handleDelete = vi.fn();
    const { container } = render(
      <ClayKeypad onKeyPress={vi.fn()} onDelete={handleDelete} onClear={vi.fn()} />
    );

    const backspaceBtn = container.querySelector('button .text-manjistha-red')?.closest('button');
    expect(backspaceBtn).not.toBeNull();

    const user = userEvent.setup();
    await user.click(backspaceBtn);
    expect(handleDelete).toHaveBeenCalledTimes(1);
  });

  it('applies custom className to the root keypad container', () => {
    const { container } = render(
      <ClayKeypad
        onKeyPress={vi.fn()}
        onDelete={vi.fn()}
        onClear={vi.fn()}
        className="custom-kiosk-class"
      />
    );

    expect(container.firstChild).toHaveClass('custom-kiosk-class');
    expect(container.firstChild).toHaveClass('grid');
    expect(container.firstChild).toHaveClass('grid-cols-3');
  });

  it('includes kiosk touch-target accessibility classes on all buttons', () => {
    render(<ClayKeypad onKeyPress={vi.fn()} onDelete={vi.fn()} onClear={vi.fn()} />);

    const buttons = screen.getAllByRole('button');
    expect(buttons).toHaveLength(12); // 1-9, clear, 0, backspace

    buttons.forEach((btn) => {
      expect(btn).toHaveClass('touch-target');
      expect(btn).toHaveClass('min-h-[56px]');
    });
  });
});
