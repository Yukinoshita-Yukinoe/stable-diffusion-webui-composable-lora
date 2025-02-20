#
# Composable-Diffusion with Lora
#
import torch
import gradio as gr

import composable_lora
import modules.scripts as scripts
from modules import script_callbacks
from modules.processing import StableDiffusionProcessing

def unload():
    torch.nn.Linear.forward = torch.nn.Linear_forward_before_lora
    torch.nn.Conv2d.forward = torch.nn.Conv2d_forward_before_lora

if not hasattr(torch.nn, 'Linear_forward_before_lora'):
    torch.nn.Linear_forward_before_lora = torch.nn.Linear.forward

if not hasattr(torch.nn, 'Conv2d_forward_before_lora'):
    torch.nn.Conv2d_forward_before_lora = torch.nn.Conv2d.forward

torch.nn.Linear.forward = composable_lora.lora_Linear_forward
torch.nn.Conv2d.forward = composable_lora.lora_Conv2d_forward

script_callbacks.on_script_unloaded(unload)

class ComposableLoraScript(scripts.Script):
    def title(self):
        return "Composable Lora"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        with gr.Group():
            with gr.Accordion("Composable Lora", open=False):
                enabled = gr.Checkbox(value=False, label="Enabled")
                opt_composable_with_step = gr.Checkbox(value=False, label="Composable LoRA with step")
                opt_uc_text_model_encoder = gr.Checkbox(value=False, label="Use Lora in uc text model encoder")
                opt_uc_diffusion_model = gr.Checkbox(value=False, label="Use Lora in uc diffusion model")
                opt_plot_lora_weight = gr.Checkbox(value=False, label="Plot the LoRA weight in all steps")
                opt_single_no_uc = gr.Checkbox(value=False, label="Don't use LoRA in uc if there're no subprompts")
                unload_ext = gr.Checkbox(value=False, label="Unload (If you got a corrupted image, try uncheck [Enabled] and checking this option and generate an image without LoRA, and then turn off this option.)")
        def enabled_changed(opt_enabled: bool, opt_unload_ext: bool):
            if opt_enabled:
                unload_ext.interactive=False
                return False
            else:
                unload_ext.interactive=True
                return opt_unload_ext
        enabled.change(enabled_changed, inputs=[enabled, unload_ext], outputs=[unload_ext]) 
        return [enabled, opt_composable_with_step, opt_uc_text_model_encoder, opt_uc_diffusion_model, opt_plot_lora_weight, opt_single_no_uc, unload_ext]

    def process(self, p: StableDiffusionProcessing, enabled: bool, opt_composable_with_step: bool, opt_uc_text_model_encoder: bool, opt_uc_diffusion_model: bool, opt_plot_lora_weight: bool, opt_single_no_uc: bool, unload_ext : bool):
        composable_lora.enabled = enabled
        composable_lora.opt_uc_text_model_encoder = opt_uc_text_model_encoder
        composable_lora.opt_uc_diffusion_model = opt_uc_diffusion_model
        composable_lora.opt_composable_with_step = opt_composable_with_step
        composable_lora.opt_plot_lora_weight = opt_plot_lora_weight
        composable_lora.opt_single_no_uc = opt_single_no_uc

        composable_lora.num_batches = p.batch_size
        composable_lora.num_steps = p.steps

        composable_lora.backup_lora_Linear_forward = torch.nn.Linear.forward
        composable_lora.backup_lora_Conv2d_forward = torch.nn.Conv2d.forward
        if (composable_lora.should_reload() or (torch.nn.Linear.forward != composable_lora.lora_Linear_forward)):
            if enabled or not unload_ext:
                torch.nn.Linear.forward = composable_lora.lora_Linear_forward
                torch.nn.Conv2d.forward = composable_lora.lora_Conv2d_forward
 
        composable_lora.reset_step_counters()

        prompt = p.all_prompts[0]
        composable_lora.load_prompt_loras(prompt)

    def process_batch(self, p: StableDiffusionProcessing, *args, **kwargs):
        composable_lora.reset_counters()

    def postprocess(self, p, processed, *args):
        torch.nn.Linear.forward = composable_lora.backup_lora_Linear_forward
        torch.nn.Conv2d.forward = composable_lora.backup_lora_Conv2d_forward
        if composable_lora.enabled:
            if composable_lora.opt_plot_lora_weight:
                processed.images.extend([composable_lora.plot_lora()])
